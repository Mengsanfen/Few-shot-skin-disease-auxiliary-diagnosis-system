from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from ..models import UserProfile
from ..forms.admin_forms import UserCreateForm, UserEditForm


def admin_required(view_func):
    """
    自定义装饰器：验证用户是否为超级管理员
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, '您没有权限访问此页面')
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def user_list_view(request):
    """用户列表视图"""
    users = UserProfile.objects.all().order_by('-date_joined')

    # 搜索功能
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(username__icontains=search_query) | \
                users.filter(real_name__icontains=search_query) | \
                users.filter(phone__icontains=search_query)

    context = {
        'users': users,
        'search_query': search_query,
        'total_users': users.count(),
        'active_users': users.filter(is_active=True).count(),
        'admin_users': users.filter(is_staff=True).count(),
    }
    return render(request, 'users/admin/user_list.html', context)


@admin_required
def user_create_view(request):
    """创建用户视图"""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # 如果上传了头像
            if request.FILES.get('avatar'):
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, f'用户 {user.username} 创建成功！')
            return redirect('users:user_list')
        else:
            messages.error(request, '创建失败，请检查输入信息')
    else:
        form = UserCreateForm()

    context = {
        'form': form,
        'title': '添加用户'
    }
    return render(request, 'users/admin/user_form.html', context)


@admin_required
def user_edit_view(request, user_id):
    """编辑用户视图"""
    user = get_object_or_404(UserProfile, id=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            # 处理新密码
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)
            # 处理头像上传
            if request.FILES.get('avatar'):
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, f'用户 {user.username} 修改成功！')
            return redirect('users:user_list')
        else:
            messages.error(request, '修改失败，请检查输入信息')
    else:
        form = UserEditForm(instance=user)

    context = {
        'form': form,
        'user_obj': user,
        'title': '编辑用户'
    }
    return render(request, 'users/admin/user_form.html', context)


@admin_required
def user_delete_view(request, user_id):
    """删除用户视图"""
    user = get_object_or_404(UserProfile, id=user_id)

    # 防止删除自己
    if user.id == request.user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': '不能删除当前登录的账户！'})
        messages.error(request, '不能删除当前登录的账户！')
        return redirect('users:user_list')

    # 防止删除超级管理员
    if user.is_superuser and request.user.id != user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': '不能删除超级管理员账户！'})
        messages.error(request, '不能删除超级管理员账户！')
        return redirect('users:user_list')

    username = user.username
    user.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'用户 {username} 已删除'})

    messages.success(request, f'用户 {username} 已删除')
    return redirect('users:user_list')


@admin_required
def user_detail_view(request, user_id):
    """用户详情视图"""
    user = get_object_or_404(UserProfile, id=user_id)

    context = {
        'user_obj': user,
    }
    return render(request, 'users/admin/user_detail.html', context)