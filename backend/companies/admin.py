from django.contrib import admin

from companies.models import Company, CompanyMember, TaxProfile


class CompanyMemberInline(admin.TabularInline):
    model = CompanyMember
    extra = 0
    autocomplete_fields = ["user"]


class TaxProfileInline(admin.TabularInline):
    model = TaxProfile
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["legal_name", "tin", "business_type", "created_at"]
    search_fields = ["legal_name", "tin"]
    inlines = [CompanyMemberInline, TaxProfileInline]
