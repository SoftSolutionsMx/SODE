from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Interest, Organization, User


@admin.register(User)
class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('SODE', {'fields': ('role', 'interests')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('SODE', {'fields': ('email', 'role')}),)
    list_display = ('email', 'role', 'is_active', 'is_staff')


admin.site.register(Organization)
admin.site.register(Interest)
