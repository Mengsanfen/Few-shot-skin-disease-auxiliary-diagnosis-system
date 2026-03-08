from django.urls import path
from .views.auth_views import register_view, login_view, logout_view
from .views.profile_views import profile_view, change_password_view
from .views.admin_views import (
    user_list_view, user_create_view, user_edit_view,
    user_delete_view, user_detail_view
)

app_name = 'users'

urlpatterns = [
    # 认证相关
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    # 个人中心
    path('profile/', profile_view, name='profile'),
    path('change-password/', change_password_view, name='change_password'),

    # 管理员 - 用户管理
    path('admin/users/', user_list_view, name='user_list'),
    path('admin/users/create/', user_create_view, name='user_create'),
    path('admin/users/<int:user_id>/edit/', user_edit_view, name='user_edit'),
    path('admin/users/<int:user_id>/delete/', user_delete_view, name='user_delete'),
    path('admin/users/<int:user_id>/', user_detail_view, name='user_detail'),
]