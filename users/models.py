from django.db import models
from django.contrib.auth.models import AbstractUser


class UserProfile(AbstractUser):
    """自定义用户模型"""

    avatar = models.ImageField(
        upload_to='avatars/',
        verbose_name='头像',
        blank=True,
        null=True,
        default='avatars/default.png'
    )
    real_name = models.CharField(
        max_length=50,
        verbose_name='真实姓名',
        blank=True,
        null=True
    )
    phone = models.CharField(
        max_length=11,
        verbose_name='手机号',
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = '用户信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username