from django.shortcuts import render
from rest_framework_simplejwt.views import TokenObtainPairView
from userauths.models import User, Profile
from userauths.serializer import MyTokenObtainPairSerializer, RegisterSerializer, UserSerializer
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
import random
import shortuuid
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

# Create your views here.

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny, )
    serializer_class = RegisterSerializer

def generate_otp():
    uuid_key = shortuuid.uuid()
    unique_key = uuid_key[:6]
    return unique_key

class PasswordResetEmailVerify(generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = UserSerializer

    def get_object(self):
        email = self.kwargs['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError({"email": "No user found with this email address."})

        if user:
            user.otp = generate_otp()
            user.save()

            uidb64 = user.pk
            otp = user.otp

            link = f"http://localhost:5173/create-new-password?otp={otp}&uidb64={uidb64}"
            # send email

            merge_data = {
                'link': link, 
                'username': user.username, 
            }

            subject = f"Password Reset Request"
            # text_body = render_to_string("email/password_reset.txt", merge_data)
            html_body = render_to_string("email/password_reset.html", merge_data)

            msg = EmailMultiAlternatives(
                subject=subject, from_email=settings.EMAIL_HOST_USER,
                to=[user.email], body=html_body
            )

            msg.attach_alternative(html_body, "text/html")
            msg.send()
        return user
    
class PasswordChangeView(generics.CreateAPIView):
    permission_classes = [AllowAny,]
    serializer_class = UserSerializer

    def create(self,request, *args, **kwargs):
        payload = request.data 
        otp = payload['otp']
        uidb64 = payload['uidb64']
        password = payload['password']

        user = User.objects.get(id=uidb64, otp=otp)
        if user:
            user.set_password(password)
            user.otp = ''
            user.reset_token = ''
            user.save()
            return Response({'detail': 'Password reset successful'}, status = status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'An Error Occured'}, status = status.HTTP_500_INTERNAL_SERVER_ERROR)
