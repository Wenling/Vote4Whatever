import cgi
import datetime
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import users

import jinja2
import os

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


#category has ancestor user
class Category(db.Model):
    name = db.CategoryProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    expiration_time = db.DateTimeProperty()

#item has ancestor category
class Item(db.Model):
    name = db.StringProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    picture = db.BlobProperty(default='img/ny.jpg')

#vote has ancestor category
class Vote(db.Model):
    voter = db.Key()
    voted_item = db.StringProperty()
    unvoted_item = db.StringProperty()
    vote_time = db.DateTimeProperty(auto_now_add=True)

class Comment(db.Model):
    commenter = db.Key()
    item = db.Key()
    create_time = db.DateTimeProperty()
    content = db.StringProperty()

class AddCat(webapp2.RequestHandler):
    def post(self):
        cat_name = self.request.get('cat_name')
        cat_expt = datetime.datetime(2013, 11, 1, 1)
        
        user_id = user_key(users.get_current_user().user_id())
        if users.get_current_user():
            cat = Category(parent=user_id, name=cat_name, expiration_time=cat_expt)
            cat.put()
#self.response.out.write(user_id)
            self.redirect('/cat_name?' + urllib.quote(cat_name))

class AddItem(webapp2.RequestHandler):
    def get(self):
        user_id = user_key(users.get_current_user().user_id())
        self.response.out.write(user_id)
#self.redirect('/?' + urllib.urlencode({'cat_name': cat_name}))

def user_key(user_id=None):
    """Constructs a Datastore key for a Guestbook entity with guestbook_name."""
    return db.Key.from_path('UserId', user_id or 'default_user')

class MainPage(webapp2.RequestHandler):
    def get(self):
        
        template_values = {}
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            username = user.nickname()
            user_id = user.user_id()

            category_query = Category.all()
            category_query.ancestor(user_key(user_id))
            cats = category_query.run()
            template_values['categories'] = cats
            
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
        template_values['username'] = username
                
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))


app = webapp2.WSGIApplication([('/', MainPage), ('/addCat', AddCat), ('/cat_name', AddItem)], debug=True)