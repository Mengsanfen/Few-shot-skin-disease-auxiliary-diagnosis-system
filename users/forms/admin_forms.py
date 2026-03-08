from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from ..models import UserProfile


class UserCreateForm(UserCreationForm):
    """管理员创建用户表单"""

    username = forms.CharField(
        label='用户名',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名'
        }),
        error_messages={
            'required': '用户名不能为空',
            'max_length': '用户名不能超过150个字符'
        }
    )

    password1 = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入密码（至少8位）'
        }),
        error_messages={
            'required': '密码不能为空'
        }
    )

    password2 = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入密码'
        }),
        error_messages={
            'required': '请确认密码'
        }
    )

    real_name = forms.CharField(
        label='真实姓名',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入真实姓名'
        })
    )

    phone = forms.CharField(
        label='手机号',
        max_length=11,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入手机号'
        })
    )

    is_active = forms.BooleanField(
        label='是否激活',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    is_staff = forms.BooleanField(
        label='是否为管理员',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['username', 'password1', 'password2', 'real_name', 'phone', 'is_active', 'is_staff']

    def clean_password1(self):
        """验证密码长度"""
        password1 = self.cleaned_data.get('password1')
        if password1 and len(password1) < 8:
            raise ValidationError('密码长度不能少于8位')
        return password1

    def clean_phone(self):
        """验证手机号格式"""
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.isdigit():
                raise ValidationError('手机号必须为数字')
            if len(phone) != 11:
                raise ValidationError('手机号必须为11位')
        return phone


class UserEditForm(forms.ModelForm):
    """管理员编辑用户表单"""

    username = forms.CharField(
        label='用户名',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入用户名'
        })
    )

    real_name = forms.CharField(
        label='真实姓名',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入真实姓名'
        })
    )

    phone = forms.CharField(
        label='手机号',
        max_length=11,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入手机号'
        })
    )

    is_active = forms.BooleanField(
        label='是否激活',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    is_staff = forms.BooleanField(
        label='是否为管理员',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    new_password = forms.CharField(
        label='新密码',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '留空则不修改密码'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['username', 'real_name', 'phone', 'is_active', 'is_staff']

    def clean_phone(self):
        """验证手机号格式"""
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.isdigit():
                raise ValidationError('手机号必须为数字')
            if len(phone) != 11:
                raise ValidationError('手机号必须为11位')
        return phone

    def clean_new_password(self):
        """验证新密码长度"""
        new_password = self.cleaned_data.get('new_password')
        if new_password and len(new_password) < 8:
            raise ValidationError('密码长度不能少于8位')
        return new_password