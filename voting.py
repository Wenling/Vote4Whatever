import cgi
import datetime
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import images

import jinja2
import os

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

class User(db.Model):
    user_id = db.StringProperty()
    user_name = db.StringProperty()

#category has ancestor user
class Category(db.Model):
    owner = db.StringProperty()
    owner_id = db.StringProperty()
    name = db.CategoryProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    expiration_time = db.DateTimeProperty()

#item has ancestor category
class Item(db.Model):
    #category = db.Key()
    name = db.StringProperty()
    rand = db.FloatProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    picture = db.BlobProperty(default='img/ny.jpg')

class Vote(db.Model):
    voter = db.Key()
    voted_item = db.Key()
    unvoted_item = db.Key()
    vote_time = db.DateTimeProperty(auto_now_add=True)

class Comment(db.Model):
    commenter = db.Key()
    item = db.Key()
    create_time = db.DateTimeProperty()
    content = db.StringProperty()

"""Used to retrieve the keys of the model given a user's information"""
def user_key(user_id=None):
    return db.Key.from_path('UserId', user_id or 'default_user')

def cat_key(user_id=None, cat_name=None):
    return db.Key.from_path('UserId', user_id, 'CatId', cat_name)

"""These functions are the models' manipulations"""
#insert a new category
def insertCat(user_id, user_name, cat_name):
    ancestor = user_key(user_id)
    cat_expt = datetime.datetime(2013, 11, 1, 1)
    cat = Category(parent=ancestor, owner=user_name, owner_id=user_id, key_name=cat_name, name=cat_name, expiration_time=cat_expt)
    cat.put()
    return cat

#list all categories under the user
def searchCat(query):
    q = Category.all()
    for k in query:
        if k=='ancestor':
            q.ancestor(query[k])
        else:
            q.filter(k, query[k])
    list = q.run()
    return list

#insert a new item, will check for the user is valid to add item in that category
def insertItem(user_id, cat_id, item_name, pic_dir):
    rand = random.random()
    item = Item(parent=cat_id, key_name=item_name, name=item_name, rand=rand)
    if pic_dir:
        item.picture = db.Blob(open(pic_dir, "rb").read())
    item.put()
    return item

#list all items under the category
def searchItem(query):
    q = Item.all()
    for k in query:
        if k=='ancestor':
            q.ancestor(query[k])
        else:
            q.filter(k, query[k])
    list = q.run()
    return list

#insert a new vote

#count all votes under the item

#get random items under the category
def pickRandom(cat_id):
    

#list all voting results under the category

class AddCat(webapp2.RequestHandler):
    def post(self):
        cat_name = self.request.get('cat_name')
        
        if users.get_current_user():
            user_id = users.get_current_user().user_id()
            user_name = users.get_current_user().nickname()
            cat = insertCat(user_id, user_name, cat_name)
            #self.response.out.write(cat_id)
            self.redirect('/?' + urllib.urlencode({'cat_name': cat.name}) + '&' + urllib.urlencode({'owner':users.get_current_user().user_id()}))

class AddItem(webapp2.RequestHandler):
    def post(self):
        user_id = users.get_current_user().user_id()
        #self.response.out.write(user_id)
        cat_name = self.request.get('cat_name')
        #self.response.out.write(cat_name)
        owner_id = self.request.get('owner')
        if owner_id == user_id:
            cat_id = cat_key(owner_id, cat_name)
            item_name = self.request.get('item_name')
            pic_dir = self.request.get('picture')
            item = insertItem(user_key(user_id), cat_id, item_name, pic_dir)
        #self.response.out.write(item.name)
        
        self.redirect('/?' + urllib.urlencode({'parent': cat_name}) + '&' + urllib.urlencode({'owner':user_id}) + '&'+ urllib.urlencode({'item_name': item_name}))

class Vote(webapp2.RequestHandler):
    def post(self):
        vote_cat = self.request.get('cat')

class Dispatcher(webapp2.RequestHandler):
    def get(self):
        
        template_values = {}
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            username = user.nickname()
            user_id = user.user_id()
            
            if self.request.arguments():
                if self.request.get('category'):
                    query = { 'ancestor' :user_key(user_id) }
                    list = searchCat(query)
                    template_values['categories'] = list
                
                elif self.request.get('cat_name'):
                    cat_name = self.request.get('cat_name')
                    owner_id = self.request.get('owner')
                    cat_id = cat_key(owner_id, cat_name)
                    query = {'ancestor' : cat_id}
                    list = searchItem(query)
                    template_values['items'] = list
                    template_values['cat_name'] = cat_name
                    template_values['owner'] = owner_id
                
                elif self.request.get('item_name'):
                    cat_name = self.request.get('parent')
                    owner_id = self.request.get('owner')
                    cat_id = cat_key(owner_id, cat_name)
                    item_name = self.request.get('item_name')
                    query = {'ancestor' : cat_id, 'name' : item_name}
                    list = searchItem(query)
                    template_values['item'] = list
                    template_values['cat_name'] = cat_name
                        
                elif self.request.get('vote_cat')=='all':
                    query = {}
                    list = searchCat(query)
                    template_values['vote_cat'] = list
            
                elif self.request.get('vote_cat'):
                    owner_id = self.request.get('owner')
                    vote_cat = self.request.get('vote_cat')
                    cat_id = cat_key(owner_id, vote_cat)
                    
            
            else:
                query = { 'ancestor' :user_key(user_id) }
                cats = searchCat(query)
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


app = webapp2.WSGIApplication([('/', Dispatcher), ('/addCat', AddCat), ('/addItem', AddItem), ('/vote', Vote)], debug=True)