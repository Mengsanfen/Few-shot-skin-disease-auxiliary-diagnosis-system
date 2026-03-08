from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from ..models import UserProfile


class RegisterForm(forms.ModelForm):
    """用户注册表单"""

    username = forms.CharField(
        label='用户名',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名',
            'autocomplete': 'off'
        }),
        error_messages={
            'required': '用户名不能为空',
            'max_length': '用户名不能超过150个字符'
        }
    )

    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码（至少8位）',
            'autocomplete': 'new-password'
        }),
        error_messages={
            'required': '密码不能为空'
        }
    )

    confirm_password = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入密码',
            'autocomplete': 'new-password'
        }),
        error_messages={
            'required': '请确认密码'
        }
    )

    class Meta:
        model = UserProfile
        fields = ['username', 'password', 'confirm_password']

    def clean_username(self):
        """验证用户名是否已存在"""
        username = self.cleaned_data.get('username')
        if UserProfile.objects.filter(username=username).exists():
            raise ValidationError('该用户名已被注册')
        return username

    def clean_password(self):
        """验证密码长度"""
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise ValidationError('密码长度不能少于8位')
        return password

    def clean(self):
        """验证两次密码是否一致"""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', '两次输入的密码不一致')

        return cleaned_data


class LoginForm(AuthenticationForm):
    """用户登录表单"""

    username = forms.CharField(
        label='用户名',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名',
            'autocomplete': 'off'
        }),
        error_messages={
            'required': '用户名不能为空'
        }
    )

    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码',
            'autocomplete': 'current-password'
        }),
        error_messages={
            'required': '密码不能为空'
        }
    )

    error_messages = {
        'invalid_login': '用户名或密码错误',
        'inactive': '该账户已被禁用',
    }