from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from rest_framework.decorators import api_view, permission_classes, action, schema
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters import rest_framework as filters

from .serializers import (UserSerializer, JWTObtainPairSerializer, JWTRefreshSerializer, UserLoginSerializer,
                          UserDetailSerializer, ChangePasswordSerializer, UserLastActivitySerializer)
from .models import User, UserFriends
from .filters import UsersFilter
from .permissions import IsProfileOwnerOrAdmin
from .schemas import UsersSchema, AuthSchema


class UsersViewSet(viewsets.ModelViewSet):
    """
    CRUD operations with active user
    retrieve:
    Return a user instance.
    You can pass id 'me' if you want to return self
    update:
    Return a user instance.
    You can pass id 'me' if you want to return self
    partial_update:
    Return a user instance.
    You can pass id 'me' if you want to return self
    """
    schema = UsersSchema(tags=['users'])
    serializer_class = UserSerializer
    detail_serializer_class = UserDetailSerializer
    change_password_serializer_class = ChangePasswordSerializer
    permission_classes = (AllowAny, IsProfileOwnerOrAdmin)

    filter_backends = (filters.DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = ('username',)
    ordering_fields = ('date_joined', 'username')
    filterset_class = UsersFilter

    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by('username')

    def get_object(self):
        if self.kwargs['pk'] == 'me':
            return self.request.user
        else:
            return super().get_object()

    def get_serializer(self, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        if self.action == 'update' or self.action == 'retrieve':
            return self.detail_serializer_class(*args, **kwargs)
        else:
            return self.serializer_class(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not request.user.is_anonymous:
            return Response({'status': 'error',
                             'message': 'you already signed up'})

        return super(UsersViewSet, self).create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Set none active status to your account
        """

        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({'status': 'success',
                         'message': 'Account is not active now'}, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=True, serializer_class=ChangePasswordSerializer,
            permission_classes=[IsAuthenticated, IsProfileOwnerOrAdmin])
    def change_password(self, request, *args, **kwargs):
        """
        Change your password.
        """

        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not instance.check_password(request.data['old_password']):
                return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
            instance.set_password(request.data['new_password'])
            instance.save()

            return Response({'status': 'success',
                             'message': 'Password updated successfully'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def add_friend(self, request, pk, *args, **kwargs):
        """Add user to your friend list"""

        if pk == 'me' or pk == request.user.id:
            return Response({'status': 'error',
                             'message': "you can't befriend yourself"})

        friends = UserFriends.objects.get_or_create(user=request.user, friend_id=pk)

        if friends[1]:
            return Response({'status': 'success',
                             'message': 'friend added'})
        else:
            return Response({'status': 'error',
                             'message': 'user already your friend'})

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def remove_friend(self, request, pk, *args, **kwargs):
        """Remove user from your friend list"""

        if pk == 'me' or pk == request.user.id:
            return Response({'status': 'error',
                             'message': "you can't remove yourself from friends"})

        friends = UserFriends.objects.filter(user=request.user, friend_id=pk).delete()

        if friends[0]:
            return Response({'status': 'success',
                             'message': 'friend removed'})
        else:
            return Response({'status': 'error',
                             'message': 'user is not your friend'})

    def _filter_serializer(self, serializer, filter_key):
        data = []
        for user in serializer.data:
            if user[filter_key]:
                data.append(user)
        return data

    def _list_response(self, serializer_filter):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self._filter_serializer(serializer, serializer_filter)
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = self._filter_serializer(serializer, serializer_filter)
        return data

    @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated])
    def friends(self, *args, **kwargs):
        """List of users that you follow and that follow you"""
        data = self._list_response(serializer_filter='is_friends')
        if hasattr(data, 'status_code'):
            return data
        return Response(data)

    @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated])
    def followers(self, *args, **kwargs):
        """List of users that follow you"""
        data = self._list_response(serializer_filter='is_follower')
        if hasattr(data, 'status_code'):
            return data
        return Response(data)

    @action(methods=['GET'], detail=False, permission_classes=[IsAuthenticated])
    def followed(self, *args, **kwargs):
        """List of users that you follow"""
        data = self._list_response(serializer_filter='is_followed')
        if hasattr(data, 'status_code'):
            return data
        return Response(data)

    @action(methods=['GET'], detail=True, permission_classes=[IsAuthenticated, IsProfileOwnerOrAdmin],
            serializer_class=UserLastActivitySerializer)
    def activity(self, *args, **kwargs):
        """
        Shows when user was logged in last time and when he made last
        request to the service.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return Response(serializer.data)


class JWTObtainPairView(TokenObtainPairView):
    """
    Takes user credentials and return refresh and access JWT
    """
    serializer_class = JWTObtainPairSerializer
    schema = AuthSchema(tags=['auth'])


class JWTRefreshView(TokenRefreshView):
    """
    Takes refresh token and return new access token
    """
    serializer_class = JWTRefreshSerializer
    schema = AuthSchema(tags=['auth'])


class JWTVerifyView(TokenVerifyView):
    """
    Takes token and check if it is valid
    """
    schema = AuthSchema(tags=['auth'])


class LoginView(GenericAPIView):
    """
    Session login.
    """
    serializer_class = UserLoginSerializer
    permission_classes = (AllowAny,)
    schema = AuthSchema(tags=['auth'])

    def post(self, request, *args, **kwargs):

        email = request.data['email']
        password = request.data['password']

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return Response({'status': 'success',
                             'message': 'logged in'}, status=status.HTTP_200_OK)
        else:
            return Response({'status': 'error',
                             'message': 'wrong email or password'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, ])
@schema(AuthSchema(tags=['auth']))
def logout_view(request):
    """
    Logout for authenticated users that using session.
    """
    logout(request)
    return Response({'status': 'success',
                     'message': 'logged out'}, status=status.HTTP_200_OK)
