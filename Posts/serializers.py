from rest_framework import serializers
from .models import Post


class PostSerializer(serializers.ModelSerializer):
    author = serializers.HiddenField(default=serializers.CreateOnlyDefault(serializers.CurrentUserDefault()))
    author_username = serializers.CharField(source='author.username', read_only=True)
    liked_by = serializers.StringRelatedField(many=True, read_only=True)
    is_liked = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()

    def get_is_liked(self, obj) -> bool:
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return obj.is_already_liked(user)

    def get_likes(self, obj) -> int:
        return obj.likes

    class Meta:
        model = Post
        fields = '__all__'


class PostAnalytics(serializers.Serializer):
    date = serializers.DateField()
    total_likes = serializers.IntegerField()
    most_likes = serializers.IntegerField()
    top_posts = serializers.ListField()


class PostInstanceAnalytics(serializers.Serializer):
    date = serializers.DateField()
    likes = serializers.IntegerField()
