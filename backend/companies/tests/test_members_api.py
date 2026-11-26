"""Members: who can see the team, who can invite, and the last-owner safety rule."""

import pytest

from accounts.tests.factories import UserFactory
from companies.models import CompanyMember, Role
from companies.tests.factories import CompanyFactory, member_of

pytestmark = pytest.mark.django_db


def members_url(company) -> str:
    return f"/api/companies/{company.pk}/members/"


def member_url(membership) -> str:
    return f"{members_url(membership.company)}{membership.pk}/"


@pytest.mark.parametrize("role", [Role.OWNER, Role.ACCOUNTANT, Role.VIEWER])
def test_any_member_can_list_the_team(client_for, role):
    m = member_of(CompanyFactory(), role)
    response = client_for(m.user).get(members_url(m.company))
    assert response.status_code == 200
    assert response.json()["results"][0]["user"]["email"] == m.user.email


def test_outsider_cannot_list_members(client_for):
    outsider = member_of(CompanyFactory())
    other = CompanyFactory()
    member_of(other)
    assert client_for(outsider.user).get(members_url(other)).status_code == 404


def test_owner_invites_existing_user_by_email(client_for):
    owner = member_of(CompanyFactory())
    invitee = UserFactory(email="kalisa@example.rw")

    response = client_for(owner.user).post(
        members_url(owner.company), {"email": "Kalisa@Example.rw", "role": "accountant"}
    )

    assert response.status_code == 201, response.json()
    assert CompanyMember.objects.get(company=owner.company, user=invitee).role == Role.ACCOUNTANT


@pytest.mark.parametrize("fmt", ["json", "multipart"])
def test_invited_member_is_active_whatever_the_request_format(client_for, fmt):
    owner = member_of(CompanyFactory())
    invitee = UserFactory()
    response = client_for(owner.user).post(
        members_url(owner.company),
        {"email": invitee.email, "role": "viewer", "is_active": False},
        format=fmt,
    )
    assert response.status_code == 201
    assert CompanyMember.objects.get(company=owner.company, user=invitee).is_active is True


@pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.VIEWER])
def test_only_owners_can_invite(client_for, role):
    m = member_of(CompanyFactory(), role)
    UserFactory(email="kalisa@example.rw")
    response = client_for(m.user).post(
        members_url(m.company), {"email": "kalisa@example.rw", "role": "viewer"}
    )
    assert response.status_code == 403


def test_invite_unknown_email_is_rejected(client_for):
    owner = member_of(CompanyFactory())
    response = client_for(owner.user).post(
        members_url(owner.company), {"email": "nobody@example.rw", "role": "viewer"}
    )
    assert response.status_code == 400
    assert "email" in response.json()


def test_cannot_invite_someone_twice(client_for):
    owner = member_of(CompanyFactory())
    existing = member_of(owner.company, Role.VIEWER)
    response = client_for(owner.user).post(
        members_url(owner.company), {"email": existing.user.email, "role": "viewer"}
    )
    assert response.status_code == 400


def test_owner_changes_role_and_deactivates(client_for):
    owner = member_of(CompanyFactory())
    m = member_of(owner.company, Role.VIEWER)
    client = client_for(owner.user)

    assert client.patch(member_url(m), {"role": "accountant"}).status_code == 200
    assert client.patch(member_url(m), {"is_active": False}).status_code == 200

    m.refresh_from_db()
    assert m.role == Role.ACCOUNTANT and m.is_active is False


def test_last_owner_cannot_be_demoted_or_deactivated(client_for):
    owner = member_of(CompanyFactory())
    client = client_for(owner.user)
    assert client.patch(member_url(owner), {"role": "viewer"}).status_code == 400
    assert client.patch(member_url(owner), {"is_active": False}).status_code == 400


def test_owner_can_step_down_when_another_owner_exists(client_for):
    owner = member_of(CompanyFactory())
    member_of(owner.company, Role.OWNER)
    response = client_for(owner.user).patch(member_url(owner), {"role": "accountant"})
    assert response.status_code == 200


def test_patch_cannot_move_membership_to_another_user(client_for):
    owner = member_of(CompanyFactory())
    m = member_of(owner.company, Role.VIEWER)
    original_user = m.user
    client_for(owner.user).patch(member_url(m), {"email": UserFactory().email})
    m.refresh_from_db()
    assert m.user == original_user


def test_cannot_edit_member_of_another_company_via_own_company_url(client_for):
    owner = member_of(CompanyFactory())
    foreign = member_of(CompanyFactory(), Role.VIEWER)
    # Real company id in the URL (owner's), but a member id from another company.
    url = f"{members_url(owner.company)}{foreign.pk}/"
    assert client_for(owner.user).patch(url, {"role": "owner"}).status_code == 404
    foreign.refresh_from_db()
    assert foreign.role == Role.VIEWER
