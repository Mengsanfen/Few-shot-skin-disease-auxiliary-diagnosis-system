from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from ..forms.profile_forms import ProfileForm, CustomPasswordChangeForm
from ..models import UserProfile


@login_required
def profile_view(request):
    """个人中心视图 - 查看和修改个人信息"""
    user = request.user

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, '个人信息修改成功！')
            return redirect('users:profile')
        else:
            messages.error(request, '修改失败，请检查输入信息')
    else:
        form = ProfileForm(instance=user)

    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'users/profile.html', context)


@login_required
def change_password_view(request):
    """修改密码视图"""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # 更新 session，防止用户被登出
            update_session_auth_hash(request, user)
            messages.success(request, '密码修改成功！')
            return redirect('users:profile')
        else:
            messages.error(request, '密码修改失败，请检查输入')
    else:
        form = CustomPasswordChangeForm(request.user)

    context = {
        'form': form,
    }
    return render(request, 'users/change_password.html', context)