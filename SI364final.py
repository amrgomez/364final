 # Import statements
import os
import requests
import json
from practice_api import api_key
from flask import Flask, render_template, session, redirect, request, url_for, flash
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from werkzeug.security import generate_password_hash, check_password_hash

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hardtoguessstring'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://localhost/SI364_FP_amrgomez" #change this later
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['HEROKU_ON'] = os.environ.get('HEROKU')

# App addition setups
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

### ASSOCIATION TABLES ###
tags= db.Table('tags', db.Column('headlines_id',db.Integer,db.ForeignKey('headlines.id')),db.Column('news_id',db.Integer, db.ForeignKey('news.id')))
user_collection= db.Table('user_collection',db.Column('newspaper_id',db.Integer,db.ForeignKey('newspaper.id')), db.Column('news_id', db.Integer, db.ForeignKey('news.id')))

##########################################################TABLES###############################################
#Users and login
class User(UserMixin, db.Model):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    #relationship with articles saved
    collections= db.relationship('Newspaper', backref= 'User')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

#run flask_login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#retrieve news sources
class News(db.Model):
    __tablename__='news'
    id=db.Column(db.Integer,primary_key= True)
    source= db.Column(db.String(356))
    url= db.Column(db.String(356)) #news story image url
    def __repr__(self):
        "Headline:{0}, URL:{1}".format(self.term,self.url)

#retrieve articles
class Newspaper(db.Model):
    __tablename__='newspaper'
    id= db.Column(db.Integer,primary_key=True)
    article= db.Column(db.String(355))
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'))
    collection= db.relationship('News', secondary= user_collection, backref= db.backref('Newspaper', lazy='dynamic'),lazy='dynamic')

#retrieve articles' headlines and urls
class Headlines(db.Model):
    __tablename__='headlines'
    id= db.Column(db.Integer, primary_key= True)
    term= db.Column(db.String(32), unique= True)
    headline= db.relationship('News', secondary=tags, backref=db.backref('Headlines',lazy='dynamic'),lazy='dynamic')
    def __repr__(self):
        return "Headlines: {0} (ID:{1})".format(self.term,self.id)

###############################################LOGIN FORMS ####################################
class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

#############################################REQUEST FORMS####################################
#Search headlines using term submitted
# class HeadlineSearch(FlaskForm):
# 	search= RadioField('Select a news source', choices=[(1,'bbc-news'),(2,'nbc-news'),(3,'cnn'),(4,'abc-news')],validators= [Required()])
# 	submit= SubmitField('Submit')

#user enters term, term is run through get_or_create_term to make request to News API for headline and story 
#image related to term
class TermSearch(FlaskForm):
    term=StringField('Enter a term', validators= [Required()])
    submit=SubmitField('Submit')

    def validate_term(self,field):
        if field.data[0] is '0':
            return ValidationError('Invalid Term')

    def validate_search_term(self, field):
        if len(field.data)== 0:
            return ValidationError('Please enter a term') 

#naming newspaper and selecting options for it
class NewsPaper(FlaskForm):
    source= StringField('Name your newspaper', validators= [Required()])
    headlines = SelectMultipleField('Choose headlines for your newspaper')
    submit= SubmitField('Submit')
class UpdateTerm(FlaskForm):
    items= StringField('Submit a new headline', validators=[Required()])
    submit=SubmitField('Update')

class UpdateButtonForm(FlaskForm):
    submit= SubmitField("Update")

class DeleteButtonForm(FlaskForm):
    submit= SubmitField("Delete")
#########################################HELPER FUNCTIONS#######################################
#find news data from search term
# def get_news_data(source):
#     l={1: 'bbc-news',2:'nbc-news',3:'cnn',4:'abc-news'}
#     baseurl= 'https://newsapi.org/v2/top-headlines?sources={}&apiKey={}'.format(l[source], api_key)
#     print(source)
#     req= requests.get(baseurl)
#     # print(req)
#     return req.json()['articles']

#making request to News API
def get_term_data(source):
    baseurl='https://newsapi.org/v2/top-headlines?q={}&apiKey={}'.format(source,api_key)
    req=requests.get(baseurl)
    print(req)
    return req.json()['articles']
#find source's website
def get_source(id):
    s = News.query.filter_by(id=id).first()
    return s
#create source's picture (using html template)
def get_or_create_pic(source,url):
    b= db.session.query(News).filter_by(source=source).first()
    if b:
        return b
    else:
        b=News(source=source, url=url)
        db.session.add(b)
        db.session.commit()
        return b
#create source select input
# def get_or_create_search_term(source):
#     searchterm= db.session.query(Headlines).filter_by(term=source).first()
#     if searchterm:
#         return searchterm
#     else:
#         searchterm= Headlines(term=source, headline=[])
#         n = get_news_data(source)
#         for y in n:
#             t = get_or_create_pic(title=y[0]['source']['name'], url=y[0:11]['urlToImage'])
#             searchterm.headline.append(t)
#         db.session.add(searchterm)
#         db.session.commit()
#         return searchterm 

#create a search term
def get_or_create_search_term(term):
    searchterm= db.session.query(Headlines).filter_by(term=term).first()
    if searchterm:
        return searchterm
    else:
        searchterm= Headlines(term=term, headline=[])
        n = get_term_data(term)
        for y in n:
            t = get_or_create_pic(source=y['title'], url=y['urlToImage'])
            searchterm.headline.append(t)
        db.session.add(searchterm)
        db.session.commit()
        return searchterm
#creates user generated newpaper
def get_or_create_newspaper(article, current_user, imgs_list=[]):
    newspaper= Newspaper.query.filter_by(article=article,user_id=current_user.id).first()
    if newspaper:
        return newspaper
    else:
        newspaper= Newspaper(article=article, user_id=current_user.id, collection=[])
        for z in imgs_list:
            newspaper.collection.append(z)
        db.session.add(newspaper)
        db.session.commit()
        return newspaper

#########################################ERROR HANDLING ############################
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

### ROUTES ###
############################################LOGIN##################################
@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/register',methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

############################################LINKS###########################################
@app.route('/', methods= ['GET','POST'])
def index():
    # form= HeadlineSearch()
    # if form.validate_on_submit():
    #     srch= form.search.data
    #     term= get_or_create_search_source(srch)
    #     return redirect(url_for('search',search_term= term.term))
    form= TermSearch()
    if form.validate_on_submit():
        srch= form.term.data
        term= get_or_create_search_term(srch)
        return redirect(url_for('headlines',search_term= term.term))
    return render_template('index.html',form=form)

#headlines for the searched term
@app.route('/headlines/<search_term>')
def headlines(search_term):
    term = Headlines.query.filter_by(term=search_term).first()
    lines = term.headline.all()
    return render_template('searched_imgs.html',imgs=lines,term=term)

#all searched terms
@app.route('/search')
def search():
    s= Headlines.query.all()
    return render_template('searched_terms.html', all_terms=s)

#all headlines/images for the searched terms
@app.route('/all_news',methods=['GET','POST'])
def all_news():
    news = News.query.all()
    form= UpdateButtonForm()
    form1= DeleteButtonForm()
    return render_template('all_headlines.html',all_news=news,form=form,form1=form1)

#create a newspaper
@app.route('/create_np', methods=['GET','POST'])
@login_required
def create_np():
    form = NewsPaper()
    imgs = News.query.all()
    choices = [(str(g.id), g.source) for g in imgs]
    form.headlines.choices = choices
    if form.validate_on_submit():
        print('Submitted')
        name=form.source.data
        headlines= form.headlines.data
        lis=[]
        for i in headlines:
            index= choices[int(i)-1][0]
            lis.append(get_source(index))
        get_or_create_newspaper(name,current_user, lis)
        return redirect(url_for('see_newspaper'))
    return render_template('create_newspaper.html', form=form)

#see the newspaper that holds the images and headlines selected
@app.route('/see_newspaper', methods=['GET','POST'])
@login_required
def see_newspaper():
    collections= Newspaper.query.filter_by(user_id= current_user.id)
    return render_template('see_newspaper.html', collections= collections)

#see the newspapers based on the order they were created
@app.route('/see_newspapers/<id_num>')
def see_newspapers(id_num):
    id_num = int(id_num)
    newspaper = Newspaper.query.filter_by(id=id_num).first()
    display = newspaper.collection.all()
    return render_template('newspaper.html',collection=newspaper, imgs= display)

#update
@app.route('/update/<item>',methods=["GET","POST"])
def update(item):
    form= UpdateTerm()
    i= News.query.filter_by(id=item).first()
    if form.validate_on_submit():
        i.source= form.items.data
        db.session.commit()
        flash("Updated headline to: " + i.source)
        return redirect(url_for('all_news'))
    return render_template('updates.html', form=form, i=i)

@app.route('/delete/<lst>',methods=["GET","POST"])
def delete(lst):
    items=News.query.filter_by(id=lst).first()
    db.session.delete(items)
    db.session.commit()
    flash('Deleted term:'+ items.source)
    return redirect(url_for('all_news'))

#########################################RUN APP #########################################
if __name__ == '__main__':
    db.create_all()
    manager.run()

