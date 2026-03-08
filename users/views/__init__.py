# 用户认证相关视图
from .auth_views import register_view, login_view, logout_view
from .profile_views import profile_view, change_password_view
from .admin_views import (
    user_list_view, user_create_view, user_edit_view,
    user_delete_view, user_detail_view
)

__all__ = [
    'register_view', 'login_view', 'logout_view',
    'profile_view', 'change_password_view',
    'user_list_view', 'user_create_view', 'user_edit_view',
    'user_delete_view', 'user_detail_view'
]