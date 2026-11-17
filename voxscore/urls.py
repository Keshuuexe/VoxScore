"""
Every VoxScore route, named so templates can use {% url 'name' %} and never a hard-coded path.
"""

from django.urls import path

from . import ai_views, auth_views, views

urlpatterns = [
    path("", views.home, name="home"),

    # Screen 1: accounts
    path("accounts/login/", auth_views.VoxLoginView.as_view(), name="login"),
    path("accounts/signup/", auth_views.SignUpView.as_view(), name="signup"),
    path("accounts/logout/", auth_views.VoxLogoutView.as_view(), name="logout"),

    # Screen 2
    path("dashboard/", views.dashboard, name="dashboard"),

    # Screens 3-5: Practice
    path("practice/", views.tuner, name="tuner"),
    path("practice/warmups/", views.warmup_list, name="warmup-list"),
    path("practice/warmups/<slug:slug>/", views.warmup_session, name="warmup-session"),
    path("practice/sessions/save/", views.session_save, name="session-save"),
    path("practice/sessions/<int:pk>/coach/", ai_views.session_coach, name="session-coach"),

    # Screens 6-7: Studio
    path("studio/", views.studio_record, name="studio-record"),
    path("studio/transcribe/", views.studio_transcribe, name="studio-transcribe"),
    path("studio/<int:pk>/", views.score_editor, name="score-editor"),
    path("studio/<int:pk>/record/", views.studio_record, name="score-record"),
    path("studio/<int:pk>/update/", views.score_update, name="score-update"),
    path("studio/<int:pk>/delete/", views.score_delete, name="score-delete"),
    path("studio/<int:pk>/export.<str:fmt>", views.score_export, name="score-export"),
    path("studio/<int:pk>/harmony/", ai_views.harmony_suggest, name="harmony-suggest"),
    path("studio/parts/<int:pk>/save/", views.part_save, name="part-save"),
    path("studio/parts/<int:pk>/delete/", views.part_delete, name="part-delete"),
    path("studio/parts/<int:pk>/accept/", views.part_accept, name="part-accept"),
    path("studio/parts/<int:pk>/reject/", views.part_reject, name="part-reject"),

    # Screen 8: Learn
    path("learn/", views.learn, name="learn-home"),
    path("learn/<slug:slug>/", views.learn, name="learn"),
    path("learn/<slug:slug>/ask/", ai_views.tutor_ask, name="tutor-ask"),

    # Screen 9: Profile
    path("profile/", views.profile, name="profile"),
    path("profile/range/", views.range_save, name="range-save"),
]
