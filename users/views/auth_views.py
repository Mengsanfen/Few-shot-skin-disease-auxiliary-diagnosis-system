from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from ..forms.auth_forms import RegisterForm, LoginForm
from ..models import UserProfile


def register_view(request):
    """用户注册视图"""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # 创建用户
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = UserProfile.objects.create_user(
                username=username,
                password=password
            )

            messages.success(request, '注册成功，请登录！')
            return redirect('login')
        else:
            # 表单验证失败，错误信息会在模板中显示
            pass
    else:
        form = RegisterForm()

    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    """用户登录视图"""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                # 保存用户状态到 session
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                request.session['is_authenticated'] = True

                messages.success(request, f'欢迎回来，{user.username}！')
                # 登录成功后跳转到首页
                return redirect('index')
            else:
                messages.error(request, '用户名或密码错误')
        else:
            messages.error(request, '登录失败，请检查输入')
    else:
        form = LoginForm()

    return render(request, 'users/login.html', {'form': form})


@login_required
def logout_view(request):
    """用户退出登录"""
    # 清除 session
    request.session.flush()
    logout(request)
    messages.info(request, '您已成功退出登录')
    return redirect('login')