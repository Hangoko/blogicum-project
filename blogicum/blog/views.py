from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from .forms import CommentForm, PostForm, UserEditForm
from .models import Category, Comment, Post

User = get_user_model()


def get_posts(posts=Post.objects, filter_published=True, annotate=True):
    posts = posts.select_related('author', 'category', 'location')
    if filter_published:
        posts = posts.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    if annotate:
        posts = posts.annotate(
            comment_count=Count('comments')
        ).order_by(*Post._meta.ordering)
    return posts


class PostListMixin:
    model = Post
    paginate_by = settings.POSTS_PER_PAGE


class IndexListView(PostListMixin, ListView):
    template_name = 'blog/index.html'

    def get_queryset(self):
        return get_posts()


class CategoryListView(PostListMixin, ListView):
    template_name = 'blog/category.html'

    def get_category(self):
        return get_object_or_404(
            Category,
            slug=self.kwargs['category_slug'],
            is_published=True,
        )

    def get_queryset(self):
        self.category = self.get_category()
        return get_posts(self.category.posts)

    def get_context_data(self, **kwargs):
        return super().get_context_data(category=self.category, **kwargs)


class ProfileListView(PostListMixin, ListView):
    template_name = 'blog/profile.html'

    def get_queryset(self):
        self.author = get_object_or_404(
            User, username=self.kwargs['username']
        )
        return get_posts(
            self.author.posts,
            filter_published=self.request.user != self.author,
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(profile=self.author, **kwargs)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    pk_url_kwarg = 'post_id'

    def get_object(self, queryset=None):
        post_id = self.kwargs[self.pk_url_kwarg]
        post = get_object_or_404(
            get_posts(filter_published=False, annotate=False), pk=post_id
        )
        if post.author == self.request.user:
            return post
        return get_object_or_404(get_posts(annotate=False), pk=post_id)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=CommentForm(),
            comments=self.object.comments.select_related('author'),
            **kwargs
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class PostAuthorMixin(LoginRequiredMixin):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        post = get_object_or_404(Post, pk=kwargs[self.pk_url_kwarg])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=post.pk)
        return super().dispatch(request, *args, **kwargs)


class PostUpdateView(PostAuthorMixin, UpdateView):
    form_class = PostForm

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.object.pk])


class PostDeleteView(PostAuthorMixin, DeleteView):

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=PostForm(instance=self.object), **kwargs
        )

    def get_success_url(self):
        return reverse('blog:profile', args=[self.request.user.username])


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm
    http_method_names = ['post']

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = get_object_or_404(
            get_posts(annotate=False), pk=self.kwargs['post_id']
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        return redirect('blog:post_detail', post_id=self.kwargs['post_id'])

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class CommentAuthorMixin(LoginRequiredMixin):
    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_object(self, queryset=None):
        comment = get_object_or_404(
            Comment,
            pk=self.kwargs[self.pk_url_kwarg],
            post_id=self.kwargs['post_id'],
        )
        if comment.author != self.request.user:
            raise Http404
        return comment

    def get_success_url(self):
        return reverse('blog:post_detail', args=[self.kwargs['post_id']])


class CommentUpdateView(CommentAuthorMixin, UpdateView):
    form_class = CommentForm


class CommentDeleteView(CommentAuthorMixin, DeleteView):
    pass
