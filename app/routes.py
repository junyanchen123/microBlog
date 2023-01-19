from app import app,db
from flask import render_template, flash, redirect,request, url_for
from app.form import LoginForm,RegistrationForm,EditProfileForm,EmptyForm,PostForm,ResetPasswordRequestForm,ResetPasswordForm
from flask_login import current_user,login_user,logout_user,login_required
from app.models import User,Post
from werkzeug.urls import url_parse
from datetime import datetime
from app.email import send_password_reset_email
import os
import secrets
from PIL import Image

@app.route('/',methods=['POST','GET'])
@app.route('/index',methods=['POST','GET'])
@login_required
def index():
    form=PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data,author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    page = request.args.get('page',1,type=int)
    posts = current_user.followed_posts().paginate(page=page,per_page=app.config['POSTS_PER_PAGE'],error_out=False)
    if posts.has_next:
        next_url=url_for('index',page=posts.next_num)
    else:
        next_url=None
    if posts.has_prev:
        prev_url=url_for('index',page=posts.prev_num)
    else:
        prev_url=None
    return render_template('index.html',title = 'Home',form=form,posts=posts.items,next_url=next_url,prev_url=prev_url)

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user,remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc!='':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html',titile='Sign In',form = form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form=RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data,email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registed user!')
        return redirect(url_for('login'))
    return render_template('register.html',title='Register',form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page=request.args.get('page',1,type=int)
    posts = user.posts.paginate(page=page,per_page=app.config['POSTS_PER_PAGE'],error_out=False)
    form=EmptyForm()
    image_file = url_for('static',filename='profile_pics/' + user.image_file)
    return render_template('user.html',user=user,posts=posts.items,form=form,image_file=image_file)

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen=datetime.utcnow()
        db.session.commit()
        
def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path,'static/profile_pics',picture_fn)
    
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    
    return picture_fn
        
@app.route('/edit_profile/<username>',methods=['GET','POST'])
@login_required
def edit_profile(username):
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        if form.image.data:
            picture_file = save_picture(form.image.data)
            current_user.image_file=picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('user',username=username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html',title='Edit Profile',form=form)

@app.route('/follow/<username>',methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('you cannot follow yourself!')
            return redirect(url_for('user',username))
        current_user.follow(user)
        db.session.commit()
        flash('You are following {}!'.format(username))
        return redirect(url_for('user',username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/unfollow/<username>',methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('you cannot follow yourself!')
            return redirect(url_for('user',username))
        current_user.unfollow(user)
        db.session.commit()
        flash('You are not following {}!'.format(username))
        return redirect(url_for('user',username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page',1,type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(page=page,per_page=app.config['POSTS_PER_PAGE'],error_out=False)
    if posts.has_next:
        next_url=url_for('explore',page=posts.next_num)
    else:
        next_url=None
    if posts.has_prev:
        prev_url=url_for('explore',page=posts.prev_num)
    else:
        prev_url=None
    return render_template('index.html',title='Explore',posts=posts.items,next_url=next_url,prev_url=prev_url)

@app.route('/reset_password_request',methods=['GET','POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',title='Reset Password',form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    print(1)
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    print(user.username)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)
