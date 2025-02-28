from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test

@login_required
@user_passes_test(lambda u: u.is_staff)
def ajustes(request):
    return render(request, 'ajustes/ajustes.html', {'title': 'Ajustes'})