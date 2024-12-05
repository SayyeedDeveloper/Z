from flask import Flask, render_template, redirect, url_for, flash, session, send_from_directory, request
from sqlalchemy.sql.functions import current_user

from config import Config
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, PasswordField, SubmitField, DateField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional
from flask_wtf.file import FileField, FileAllowed, FileRequired
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fname = db.Column(db.String(), nullable=False)
    sname = db.Column(db.String(), nullable=False)
    uname = db.Column(db.String(), nullable=False, unique=True)
    email = db.Column(db.String(), nullable=False, unique=True)
    pswd = db.Column(db.String(), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    followers = db.relationship(
        'Follow',
        foreign_keys='Follow.followed_id',
        backref='followed_user',
        lazy='dynamic'
    )

    followed = db.relationship(
        'Follow',
        foreign_keys='Follow.follower_id',
        backref='follower_user',
        lazy='dynamic'
    )


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    picture = db.Column(db.String(), nullable=True)
    title = db.Column(db.String(), nullable=False)
    content = db.Column(db.Text, nullable=False)
    datetime = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


with app.app_context():
    db.create_all()

class SignUpForm(FlaskForm):
    fname = StringField('First name', validators=[DataRequired()])
    sname = StringField('Last name', validators=[DataRequired()])
    uname = StringField('Username', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    email_confirm = EmailField('Confirm Email', validators=[
        DataRequired(),
        EqualTo('email', message='Emails must match')
    ])
    pswd = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField()

    def validate_email(self, email):
        existing_user = User.query.filter_by(email=email.data).first()
        if existing_user:
            raise ValidationError("This email is already registered. Please use another email.")

    def validate_uname(self, uname):
        existing_user = User.query.filter_by(uname=uname.data).first()
        if existing_user:
            raise ValidationError("This username is already taken. Please choose another username.")


class SignInForm(FlaskForm):
    email_or_username = StringField('Email or Username', validators=[DataRequired()])
    pswd = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class PostForm(FlaskForm):
    picture = FileField('Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!'), Optional()])
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    datetime = DateField('Date', validators=[DataRequired()])
    submit = SubmitField()



@app.route('/user_files/<filename>')
def user_files(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def main():
    if 'user' in session:
        posts = Post.query.all()
        users = User.query.all()

        current_user = User.query.filter_by(id=session['user']).first()
        follow_status = {}
        for author in users:
            # Check if the current user is following this author
            is_following = db.session.query(Follow).filter_by(follower_id=current_user.id, followed_id=author.id).first() is not None
            follow_status[author.id] = is_following

        return render_template('index.html',
                               posts=posts,
                               users=users,
                               current_user=current_user,
                               follow_status=follow_status
                               )
    else:
         return redirect(url_for('sign_in'))

@app.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    form = SignUpForm()
    if form.validate_on_submit():
        # Extract form data
        fname = form.fname.data
        sname = form.sname.data
        uname = form.uname.data
        email = form.email.data
        pswd = form.pswd.data

        # Create and save new user
        user = User(fname=fname, sname=sname, uname=uname, email=email, pswd=pswd)
        db.session.add(user)
        db.session.commit()
        session['user'] = user.id
        return redirect(url_for('main'))

    return render_template('signUp.html', form=form)


@app.route('/sign-in', methods=['GET', 'POST'])
def sign_in():
    form = SignInForm()
    if form.validate_on_submit():
        # Check if the input matches either email or username
        user = User.query.filter(
            (User.email == form.email_or_username.data) |
            (User.uname == form.email_or_username.data)
        ).first()

        if not user:
            form.email_or_username.errors.append("No account found with this email or username.")
        elif user.pswd != form.pswd.data:
            form.pswd.errors.append("Incorrect password. Please try again.")
        else:
            session['user'] = user.id
            return redirect(url_for('main'))

    return render_template('signIn.html', form=form)

@app.route('/sign-out')
def sign_out():
    session.pop('user', None)
    return redirect(url_for('main'))

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' in session:
        user = User.query.filter_by(id=session['user']).first()
        form = SignUpForm(obj=user)
        if form.validate_on_submit():
            user.fname = form.fname.data
            user.sname = form.sname.data
            user.uname = form.uname.data
            user.email = form.email.data
            user.pswd = form.pswd.data
            db.session.commit()
            return redirect(url_for('main'))
        else:
            form.fname.data = user.fname
            form.sname.data = user.sname
            form.uname.data = user.uname
            form.email.data = user.email
            form.pswd.data = user.pswd
            return render_template('editProfile.html', form=form)
    else:
        return redirect(url_for('sign_in'))

@app.route('/create-post', methods=['GET', 'POST'])
def create_post():
    if 'user' in session:
        form = PostForm()
        if form.validate_on_submit():
            picture = form.picture.data
            title = form.title.data
            content = form.content.data
            datetime = form.datetime.data
            user_id = session['user']


            print(f"Form Data -> Title: {title}, Content: {content}, Date: {datetime}, User ID: {user_id}")

            # Check if the post already exists
            duplicate_post = Post.query.filter_by(
                title=title,
                content=content,
                datetime=datetime,
                user_id=user_id
            ).first()

            print(f"Duplicate Post Check -> {duplicate_post}")

            if not duplicate_post:
                post = Post(title=title, content=content, user_id=user_id, datetime=datetime, picture=picture.filename)
                picture.save(os.path.join(app.config['UPLOAD_FOLDER'], picture.filename))
                db.session.add(post)
                db.session.commit()
            else:
                flash("You have already created this post.")
                return render_template('createPost.html', form=form)

            return redirect(url_for('main'))
        return render_template('createPost.html', form=form)
    else:
        return redirect(url_for('sign_in'))

@app.route('/delete-post/<int:id>')
def delete_post(id):
    if 'user' in session:
        post = Post.query.filter_by(id=id).first()
        if post.user_id == session['user']:

            image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.picture)
            if os.path.exists(image_path):
                os.remove(image_path)

            db.session.delete(post)
            db.session.commit()
        return redirect(url_for('main'))
    else:
        return redirect(url_for('sign_in'))



@app.route('/edit-post/<int:id>', methods=['GET', 'POST'])
def edit_post(id):
    if 'user' in session:
        post = Post.query.filter_by(id=id).first()
        if post.user_id == session['user']:
            form = PostForm(obj=post)
            if form.validate_on_submit():
                # Update title, content, and datetime
                post.title = form.title.data
                post.content = form.content.data
                post.datetime = form.datetime.data

                # Handle picture upload
                if 'picture' in request.files:
                    picture = request.files['picture']
                    if picture.filename:  # A new file is uploaded
                        # Remove old picture
                        if post.picture:
                            old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], post.picture)
                            if os.path.exists(old_image_path):
                                os.remove(old_image_path)

                        # Save new picture
                        picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture.filename)
                        picture.save(picture_path)
                        post.picture = picture.filename

                db.session.commit()
                return redirect(url_for('main'))

            return render_template('editPost.html', form=form)

    return redirect(url_for('sign_in'))

@app.route('/follow/<int:id>')
def follow(id):
    if 'user' in session:
        follower_id = session['user']
        followed_id = id
        follow = Follow(follower_id=follower_id, followed_id=followed_id)
        db.session.add(follow)
        db.session.commit()
        return redirect(url_for('main'))
    else:
        return redirect(url_for('sign_in'))

@app.route('/unfollow/<int:id>')
def unfollow(id):
    if 'user' in session:
        follower_id = session['user']
        followed_id = id
        follow = Follow.query.filter_by(follower_id=follower_id, followed_id=followed_id).first()
        db.session.delete(follow)
        db.session.commit()
        return redirect(url_for('main'))
    else:
        return redirect(url_for('sign_in'))


@app.route('/following')
def following():
    if 'user' in session:
        users = User.query.all()
        user = User.query.filter_by(id=session['user']).first()
        current_user = User.query.filter_by(id=session['user']).first()
        following = user.followed.all()  # List of Follow objects
        followed_users = [User.query.get(f.followed_id) for f in following]  # Resolve Followed Users

        # Get posts by followed users
        followed_user_ids = [f.followed_id for f in following]  # Extract user IDs of followed users
        posts = Post.query.filter(Post.user_id.in_(followed_user_ids)).all()  # Query posts by those users

        follow_status = {}
        for author in users:
            # Check if the current user is following this author
            is_following = db.session.query(Follow).filter_by(follower_id=current_user.id, followed_id=author.id).first() is not None
            follow_status[author.id] = is_following

        print(f"Following -> {following}")  # Debugging
        print("All Follows: ", Follow.query.all())
        print("Following relationships:", [f.id for f in following])
        print("Followed users:", [user.uname for user in followed_users])
        print("Followed posts:", posts)  # Debugging

        return render_template('following.html', posts=posts, users=users, current_user=current_user, follow_status=follow_status)
    else:
        return redirect(url_for('sign_in'))

@app.route('/datas')
def datas():
    if 'user' in session:
        posts = Post.query.all()
        users = User.query.all()
        current_user = User.query.filter_by(id=session['user']).first()
        following = current_user.followed.all()

        followed_user_ids = [f.followed_id for f in following]
        following_posts = Post.query.filter(Post.user_id.in_(followed_user_ids)).all()

        print(current_user)
        print(following)
        print(following_posts)

        return render_template('datas.html', following=following, following_posts=following_posts, users=users, posts=posts)


if __name__ == '__main__':
    app.run(debug=True)