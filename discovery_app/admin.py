from django.contrib import admin
from .models import RecommendationParameter


@admin.register(RecommendationParameter)
class RecommendationParameterAdmin(admin.ModelAdmin):
    list_display = ('name', 'value', 'description', 'updated_at')
    list_editable = ('value',)
    search_fields = ('name', 'description')
    ordering = ('name',)
