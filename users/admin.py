from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    """用户模型后台管理"""

    list_display = ['username', 'real_name', 'phone', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['username', 'real_name', 'phone']

    # 添加自定义字段到编辑页面
    fieldsets = UserAdmin.fieldsets + (
        ('个人信息', {'fields': ('avatar', 'real_name', 'phone')}),
    )

    # 添加自定义字段到添加页面
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('个人信息', {'fields': ('avatar', 'real_name', 'phone')}),
    )