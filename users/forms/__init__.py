from .auth_forms import RegisterForm, LoginForm
from .profile_forms import ProfileForm, CustomPasswordChangeForm
from .admin_forms import UserCreateForm, UserEditForm

__all__ = [
    'RegisterForm', 'LoginForm',
    'ProfileForm', 'CustomPasswordChangeForm',
    'UserCreateForm', 'UserEditForm'
]