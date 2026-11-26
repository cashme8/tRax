from django.db import transaction
from rest_framework import serializers

from accounts.models import User, normalize_email
from accounts.serializers import UserSerializer
from companies.models import Company, CompanyMember, Role, TaxProfile


class TaxProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxProfile
        fields = [
            "id",
            "tax_regime",
            "vat_registered",
            "filing_frequency",
            "effective_from",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_effective_from(self, value):
        company = self.context.get("company")
        if company and company.tax_profiles.filter(effective_from=value).exists():
            raise serializers.ValidationError("A tax profile already starts on this date.")
        return value


class CompanySerializer(serializers.ModelSerializer):
    # Sent once, when creating the company. Later changes go through
    # /api/companies/<id>/tax-profiles/ so the history is kept.
    tax_profile = TaxProfileSerializer(write_only=True, required=False)
    current_tax_profile = serializers.SerializerMethodField()
    my_role = serializers.CharField(read_only=True)  # annotated by the view

    class Meta:
        model = Company
        fields = [
            "id",
            "legal_name",
            "tin",
            "business_type",
            "industry",
            "my_role",
            "current_tax_profile",
            "tax_profile",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_current_tax_profile(self, company: Company) -> dict | None:
        profile = company.tax_profile_on()
        return TaxProfileSerializer(profile).data if profile else None

    def validate(self, attrs: dict) -> dict:
        if self.instance is None and "tax_profile" not in attrs:
            raise serializers.ValidationError({"tax_profile": "Required when creating a company."})
        if self.instance is not None and "tax_profile" in attrs:
            raise serializers.ValidationError(
                {"tax_profile": "Add a new tax profile via the tax-profiles endpoint instead."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Company:
        """Create the company, make the creator its owner, and store its first tax profile."""
        tax_profile_data = validated_data.pop("tax_profile")
        company = Company.objects.create(**validated_data)
        CompanyMember.objects.create(
            company=company, user=self.context["request"].user, role=Role.OWNER
        )
        TaxProfile.objects.create(company=company, **tax_profile_data)
        company.my_role = Role.OWNER
        return company


class CompanyMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    # Inviting: give the email of someone who already has a tRax account.
    # TODO(later): email invitations for people without an account yet.
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = CompanyMember
        fields = ["id", "user", "email", "role", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:  # updating: role / is_active only, not who it is
            fields["email"].read_only = True
        else:
            # New members are always active. (DRF reads a boolean left out of an
            # HTML-form POST as False, which would silently invite someone switched off.)
            fields["is_active"].read_only = True
        return fields

    def validate_email(self, value: str) -> User:
        user = User.objects.filter(email=normalize_email(value), is_active=True).first()
        if user is None:
            raise serializers.ValidationError(
                "No tRax user has this email. Ask them to register first."
            )
        if CompanyMember.objects.filter(company=self.context["company"], user=user).exists():
            raise serializers.ValidationError("This person is already a member of this company.")
        return user

    def validate(self, attrs: dict) -> dict:
        member = self.instance
        if member is not None and member.role == Role.OWNER and member.is_active:
            losing_owner = attrs.get("role", Role.OWNER) != Role.OWNER or not attrs.get(
                "is_active", True
            )
            other_owners = CompanyMember.objects.filter(
                company=member.company, role=Role.OWNER, is_active=True
            ).exclude(pk=member.pk)
            if losing_owner and not other_owners.exists():
                raise serializers.ValidationError("A company must keep at least one active owner.")
        return attrs

    def create(self, validated_data: dict) -> CompanyMember:
        user = validated_data.pop("email")
        return CompanyMember.objects.create(
            company=self.context["company"], user=user, **validated_data
        )
