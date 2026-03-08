from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from ..models import UserProfile


class ProfileForm(forms.ModelForm):
    """用户信息修改表单"""

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

    avatar = forms.ImageField(
        label='头像',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['real_name', 'phone', 'avatar']

    def clean_phone(self):
        """验证手机号格式"""
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.isdigit():
                raise ValidationError('手机号必须为数字')
            if len(phone) != 11:
                raise ValidationError('手机号必须为11位')
        return phone


class CustomPasswordChangeForm(PasswordChangeForm):
    """自定义修改密码表单"""

    old_password = forms.CharField(
        label='原密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入原密码',
            'autocomplete': 'current-password'
        }),
        error_messages={
            'required': '请输入原密码'
        }
    )

    new_password1 = forms.CharField(
        label='新密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入新密码（至少8位）',
            'autocomplete': 'new-password'
        }),
        error_messages={
            'required': '请输入新密码'
        }
    )

    new_password2 = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '请再次输入新密码',
            'autocomplete': 'new-password'
        }),
        error_messages={
            'required': '请确认新密码'
        }
    )

    def clean_new_password1(self):
        """验证新密码长度"""
        new_password1 = self.cleaned_data.get('new_password1')
        if new_password1 and len(new_password1) < 8:
            raise ValidationError('密码长度不能少于8位')
        return new_password1

    def clean(self):
        """验证两次新密码是否一致"""
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error('new_password2', '两次输入的新密码不一致')

        return cleaned_data