"""DM-AI URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from app01.views import index, mask, screen, lung, tips, chat, cell, agent

urlpatterns = [
    # path('admin/', admin.site.urls),
    # 用户认证
    path('', include('users.urls')),
    path('', index.entrance),
    path('index/', index.index, name='index'),
    #ai问诊
    path('ai-chat/', chat.ai_chat, name='ai_chat'),  # AI问诊主界面
    path('ai-chat/process/', chat.ai_process, name='ai_process'),  # 问诊处理接口

    # agent-deepseek
    path('agent/', agent.ai_diagnosis, name="ai_diagnosis"),
    path('agent/chat/', agent.chat_message, name="agent_chat_message"),
    path('agent/chat/stream/', agent.chat_message_stream, name="agent_chat_message_stream"),
    path('agent/conversation/new/', agent.new_conversation, name="agent_new_conversation"),
    path('agent/conversation/<int:conversation_id>/', agent.conversation_detail, name="agent_conversation_detail"),
    path('agent/conversation/<int:conversation_id>/clear/', agent.clear_conversation, name="agent_clear_conversation"),
    path('agent/graph/query/', agent.graph_query, name="agent_graph_query"),
    #口罩检测==》细胞检测
    path('mask/', mask.mask_index),
    path('mask/upload/', mask.mask_upload),
    path('mask/img/', mask.mask_img),

    # 细胞检测 用api版
    path('cell/', cell.index, name='cell_index'),
    path('cell/detect/', cell.detect, name='cell_detect'),

    # 皮肤病分类诊断 (SFEPT)
    path('screen/', screen.index),
    path('lungkonw/', lung.lungkonw),
    path('diagnose_skin/', lung.skin_disease_index, name='skin_disease_index'),
    path('diagnose_skin/upload/', lung.skin_disease_upload, name='skin_disease_upload'),
    path('diagnose_skin/predict/', lung.skin_disease_predict, name='skin_disease_predict'),
    # 健康科普
    path('medical/', tips.medical),
    path('medical/data/', tips.get_medical),
    path('medical/knowledge/list/', tips.knowledge_list, name='knowledge_list'),
    path('medical/knowledge/<int:entry_id>/', tips.knowledge_detail, name='knowledge_detail'),
    path('medical/knowledge/save/', tips.knowledge_save, name='knowledge_save'),
    path('medical/knowledge/<int:entry_id>/delete/', tips.knowledge_delete, name='knowledge_delete'),
    path('medical/knowledge/import-builtin/', tips.knowledge_import_builtin, name='knowledge_import_builtin'),
    path('medical/knowledge/retrieve/', tips.knowledge_retrieve, name='knowledge_retrieve'),
    path('medical/knowledge/documents/', tips.knowledge_document_list, name='knowledge_document_list'),
    path('medical/knowledge/documents/upload/', tips.knowledge_document_upload, name='knowledge_document_upload'),
    path('medical/knowledge/documents/<int:document_id>/delete/', tips.knowledge_document_delete, name='knowledge_document_delete'),
    path('health/', tips.health),
    path('protect/', tips.protect),
    path('air/data/', tips.get_air),
    path('tips/data/', tips.get_coup),
    path('get_tips/', tips.get_tips, name='get_tips'),


]


# 开发环境下添加media路由
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
