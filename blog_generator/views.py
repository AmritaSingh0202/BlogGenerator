from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import os
from pytube import YouTube
import assemblyai as aai
import openai
from .models import BlogPost
from django.conf import settings

# API keys
ASSEMBLYAI_API_KEY = "9375340f26994335856227f1a092acdf"
OPENAI_API_KEY = "sk-kUTBHzUV1f5eLDLnz6NYBvh5RrpT5-z0LoHKqciHDfT3BlbkFJfjpGPy-H6y5IKcrenRgqw2ucdqgFzaHQTBRlsVEI0A"

@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # Get YouTube video title
        title = yt_title(yt_link)

        # Get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)

        # Debugging output
        print(f"Transcription: {transcription}")

        # Use OpenAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        # Debugging output
        print(f"Generated Blog Content: {blog_content}")

        # Save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # Return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    try:
        yt = YouTube(link)
        title = yt.title
        return title
    except Exception as e:
        print(f"Error fetching YouTube title: {e}")
        return "Unknown Title"

def download_audio(link):
    try:
        yt = YouTube(link)
        video = yt.streams.filter(only_audio=True).first()
        if not video:
            print("No audio stream available for this video.")
            return None

        out_file = video.download(output_path=settings.MEDIA_ROOT)  # type: ignore
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        os.rename(out_file, new_file)
        return new_file
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def get_transcription(link):
    audio_file = download_audio(link)
    if not audio_file:
        return None

    aai.settings.api_key = ASSEMBLYAI_API_KEY
    try:
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_file)
        print(f"Transcript: {transcript.text}")  # Debugging line
        if not transcript.text:
            print("No transcription text received.")
        return transcript.text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None

def generate_blog_from_transcription(transcription):
    openai.api_key = OPENAI_API_KEY
    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article. Write it based on the transcript, but don’t make it look like a YouTube video; make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=1000
        )
        print(f"OpenAI Response: {response}")  # Debugging line
        if response.choices:
            generated_content = response.choices[0].text.strip()
            if not generated_content:
                print("Generated content is empty.")
            return generated_content
        else:
            print("No choices in response.")
            return None
    except Exception as e:
        print(f"Error during blog generation: {e}")
        return None

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    try:
        blog_article_detail = BlogPost.objects.get(id=pk)
        if request.user == blog_article_detail.user:
            return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
        else:
            return redirect('/')
    except BlogPost.DoesNotExist:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except Exception as e:
                error_message = f'Error creating account: {e}'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
