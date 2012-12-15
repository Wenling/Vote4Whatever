from __future__ import with_statement
import cgi
import datetime
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import files

import jinja2
import os
import random
import operator
import xml.dom.minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement, Comment

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

#vote has ancestor item
class Vote(db.Model):
    voter = db.StringProperty()
    #voted_item = db.ReferenceProperty(Item)
    favored = db.BooleanProperty()
    vote_time = db.DateTimeProperty(auto_now_add=True)

#comment has ancestor item
class Comment(db.Model):
    commenter_id = db.StringProperty()
    commenter = db.StringProperty()
    create_time = db.DateTimeProperty(auto_now_add=True)
    content = db.StringProperty()

"""Used to retrieve the keys of the model given a user's information"""
def user_key(user_id=None):
    return db.Key.from_path('UserId', user_id or 'default_user')

def cat_key(user_id=None, cat_name=None):
    return db.Key.from_path('UserId', user_id, 'CatId', cat_name)

def item_key(cat_id=None, item_name=None):
    return db.Key.from_path('CatId', cat_id, 'ItemId', item_name)

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
    return q

#insert a new item, will check for the user is valid to add item in that category
def insertItem(cat_id, item_name, pic_dir):
    randnum = random.random()
    item = Item(parent=cat_id, key_name=item_name, name=item_name, rand=randnum)
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
        elif k=='rand':
            q.filter('Item.rand >=', query[k])
        else:
            q.filter(k, query[k])
    return q

#insert a new vote
def insertVote(voter, voted_item_id, favored):
    vote = Vote(parent=voted_item_id, favored=favored, voter=voter)
    vote.put()
    return vote

#list all votes under the item
def searchVote(query):
    q = Vote.all()
    for k in query:
        if k=='ancestor':
            q.ancestor(query[k])
        else:
            q.filter(k, query[k])
    return q

#remove all votes given the item
@db.transactional
def removeVote(query):
    list = searchVote(query)
    db.delete(list)    

#remove the item give id
@db.transactional
def removeItem(query):
    list = searchItem(query)
    db.delete(list)

#remove the category given category id
@db.transactional
def removeCategory(query):
    list = searchCat(query)
    db.delete(list)

#insert comment given item id
def insertComment(commenter, commenter_id, item_id, content):
    comment = Comment(parent=item_id, commenter = commenter, commenter_id = commenter_id, content = content)
    comment.put()
    return comment

#search comments given query
def searchComment(query):
    q = Comment.all()
    for k in query:
        if k=='ancestor':
            q.ancestor(query[k])
        else:
            q.filter(k, query[k])
    return q

#get random items under the category
def pickRandom(cat_id):
    r = random.random()
    q = Item.all()
    q.ancestor(cat_id).filter('rand >=', r).order('rand')
    return q.get()

#count all votes under the item
def countVote(query):
    q = db.Query(Vote)
    for k in query:
        if k=='ancestor':
            q.ancestor(query[k])
        else:
            q.filter(k, query[k])
    num = q.count()
    return num

#list all voting results under the category
def listResult(owner_id, cat_name, user_id):
    results = {}
    not_voted = {}
    cat_id = cat_key(owner_id, cat_name)
    query = {'ancestor':cat_id}
    items = searchItem(query).run()
    for item in items:
        item_id = item_key(owner_id + '/' + cat_name, item.name)
        q_favored = {'ancestor' : item_id, 'favored' : True}
        favored_count = countVote(q_favored)
        q_un = {'ancestor' : item_id, 'favored' : False}
        un_count = countVote(q_un)
        
        if favored_count == 0 and un_count == 0:
            percent = 0
            not_voted[item.name] = [0, 0, '-']
        else:        
            percent = favored_count / (0.0 + favored_count + un_count)
            results[item.name] = [favored_count, un_count, percent]
    
    return results, not_voted

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
        """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = xml.dom.minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

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
            item = insertItem(cat_id, item_name, pic_dir)
        #self.response.out.write(item.name)
        
        self.redirect('/?' + urllib.urlencode({'parent': cat_name}) + '&' + urllib.urlencode({'owner':user_id}) + '&'+ urllib.urlencode({'item_name': item_name}))

class VoteItem(webapp2.RequestHandler):
    def get(self):
        cat_name = self.request.get('cat_name')
        owner_id = self.request.get('owner')
        user_id = users.get_current_user().user_id()
        cat_id = owner_id + '/' + cat_name
        
        if self.request.get('item_name'):
            item_name = self.request.get('item_name')
            unvoted_item = self.request.get('unvote_item')
            item1_id = item_key(cat_id, item_name)
            item2_id = item_key(cat_id, unvoted_item)
            vote1 = insertVote(user_id, item1_id, True)
            vote2 = insertVote(user_id, item2_id, False)
        
            self.redirect('/?' + urllib.urlencode({'prev1' : item_name}) + '&' + urllib.urlencode({'prev2' : unvoted_item}) + '&' + urllib.urlencode({'vote_cat': cat_name}) + '&' + urllib.urlencode({'owner':user_id}))
        
        elif self.request.get('not_skip'):
            not_skip = self.request.get('not_skip')
            item = self.request.get('item')
            skip_item = self.request.get('skip_item')
            
            #self.response.out.write(item)
#self.response.out.write(skip_item)

            self.redirect('/?' + urllib.urlencode({'not_skip': not_skip}) + '&' + urllib.urlencode({'item': item}) + '&' + urllib.urlencode({'skip_item': skip_item}) + '&' + urllib.urlencode({'vote_cat': cat_name}) + '&' + urllib.urlencode({'owner':user_id}))

class ImportCat(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        #try:
            upload = self.get_uploads()[0]
            blob_key=upload.key()
            blob_reader = blobstore.BlobReader(blob_key)
            document = blob_reader.read()
            dom = xml.dom.minidom.parseString(document)
            cat_name = dom.getElementsByTagName("NAME")[0]
            user_id = users.get_current_user().user_id()
            user_name = users.get_current_user().nickname()
            
            name = getText(cat_name.childNodes)
            cat = insertCat(user_id, user_name, name)
            items = dom.getElementsByTagName("ITEM")
    
            for item in items:
                cat_id = cat_key(user_id, name)
                item_name = getText(item.getElementsByTagName("NAME")[0].childNodes)
                #haven't save images
                insertItem(cat_id, item_name,None)
            self.redirect('/?category=a')
        
                #except:
#self.redirect('/?upload_failure=true&categories=a')

class ExportHandler(webapp2.RequestHandler):    
    def get(self):
        cat_name = self.request.get('cat_name')
        owner_id = self.request.get('owner')
        self.response.out.write(cat_name)
        
        cat_id = cat_key(owner_id, cat_name)
        query = {'ancestor' : cat_id}
        list = searchItem(query)
    
        # make items into xml
        top = ElementTree.Element('top')
    
        comment = ElementTree.Comment('Generated automatically by 1010Ling.')
        top.append(comment)
    
        child = SubElement(top, 'NAME')
        child.text = cat_name
    
        for item in list:
            i = SubElement(top, 'ITEM')
            name = SubElement(i, 'NAME')
            name.text = item.name
            create_time = SubElement(i, 'CREATE_TIME')
            create_time.text = item.create_time.ctime()
            #pic = SubElement(i, 'PICTURE')
            #pic.text = blobstore.BlobInfo.get(item.picture).dump()
    
        data = prettify(top)
    
        # Create the file
        file_name = files.blobstore.create(mime_type='application/octet-stream')
    
        # Open the file and write to it
        with files.open(file_name, 'a') as f:
            f.write(data)
    
        # Finalize the file. Do this before attempting to read it.
        files.finalize(file_name)
    
        # Get the file's blob key
        blob_key = files.blobstore.get_blob_key(file_name)
        self.redirect('/export/%s' % blob_key)

class ExportCat(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, file_key):
        if not blobstore.get(file_key):
            self.error(404)
        else:
            self.send_blob(file_key)
            #self.response.out.write(file_key)

class AddComment(webapp2.RequestHandler):
    def post(self):
        user_id = users.get_current_user().user_id()
        user_name = users.get_current_user().nickname()
        #self.response.out.write(user_id)
        cat_name = self.request.get('cat_name')
        #self.response.out.write(cat_name)
        owner_id = self.request.get('owner')
        item_name = self.request.get('item_name')
        #self.response.out.write(item_name)
        content = self.request.get('content')
        item_id = item_key(owner_id+'/'+cat_name, item_name)
        insertComment(user_name, user_id, item_id, content)
        
        self.redirect('/?item_name=' + item_name + '&' + urllib.urlencode({'parent': cat_name}) + '&' + urllib.urlencode({'owner':owner_id}))

class Dispatcher(webapp2.RequestHandler):
    def get(self):
        
        template_values = {}
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            username = user.nickname()
            user_id = user.user_id()
            
            template_values['username'] = username
            template_values['user_id'] = user_id
            
            if self.request.arguments():
                if self.request.get('category'):
                    if self.request.get('category')=='all':
                        query = {}
                        list = searchCat(query)
                        template_values['view'] = True
    
                    else:
                        query = { 'ancestor' :user_key(user_id) }
                        list = searchCat(query)
                        upload_url = blobstore.create_upload_url('/import')
                        template_values['import'] = upload_url
                        template_values['view'] = False
                
                    template_values['categories'] = list
                
                elif self.request.get('cat_name'):
                    cat_name = self.request.get('cat_name')
                    owner_id = self.request.get('owner')
                    cat_id = cat_key(owner_id, cat_name)
                    query = {'ancestor' : cat_id}
                    list = searchItem(query).run()
                    template_values['items'] = list
                    template_values['cat_name'] = cat_name
                    template_values['owner'] = owner_id
                
                elif self.request.get('item_name'):
                    cat_name = self.request.get('parent')
                    owner_id = self.request.get('owner')
                    cat_id = cat_key(owner_id, cat_name)
                    item_name = self.request.get('item_name')
                    query = {'ancestor' : cat_id, 'name' : item_name}
                    item = searchItem(query).get()
                    
                    item_id = item_key(owner_id+'/'+cat_name, item_name)
                    q_comment = {'ancestor' : item_id}
                    comments = searchComment(q_comment).run()
                    
                    template_values['item'] = item
                    template_values['cat_name'] = cat_name
                    template_values['owner'] = owner_id
                    template_values['comments'] = comments
                        
                elif self.request.get('vote_cat')=='all':
                    query = {}
                    list = searchCat(query)
                    template_values['vote_cat'] = list
            
                elif self.request.get('vote_cat'):
                    owner_id = self.request.get('owner')
                    vote_cat = self.request.get('vote_cat')
                    cat_id = cat_key(owner_id, vote_cat)
                    
                    template_values['vote'] = []
                    
                    not_skip = 0
                    if self.request.get('not_skip'):
                        not_skip = self.request.get('not_skip')
                        skip_item = self.request.get('skip_item')
                        query = {'ancestor' : cat_id, 'name' : self.request.get('item')}
                        item1 = searchItem(query).get()
                        self.response.out.write(item1)
                    
                        item2 = pickRandom(cat_id)
                        while (not item2) or (item2 and item2.name == item1.name) or (item2.name == skip_item):
                            item2 = pickRandom(cat_id)
            
                    elif self.request.get('prev1'):
                        prev1 = self.request.get('prev1')
                        prev2 = self.request.get('prev2')
                        template_values['prev1'] = prev1
                        template_values['prev2'] = prev2
                        
                        item1 = pickRandom(cat_id)
                        while (not item1) or (item1 and item1.name == prev1) or (item1 and item1.name == prev2):
                            item1 = pickRandom(cat_id)
                        
                        item2 = pickRandom(cat_id)
                        while (not item2) or (item2 and item2.name == item1.name) or (item2 and item2.name == prev2) or (item2 and item2.name == prev1):
                            item2 = pickRandom(cat_id)                                               
                                                  
                    else:
                        item1 = pickRandom(cat_id)
                        while not item1:
                            item1 = pickRandom(cat_id)
                            
                        item2 = pickRandom(cat_id)
                        while (not item2) or (item2 and item2.name == item1.name):
                            item2 = pickRandom(cat_id)
            
                    if not_skip == 1:
                        template_values['vote'] = [item1, item2]
                    else:
                        template_values['vote'] = [item2, item1]
        
                    template_values['owner'] = owner_id
                    template_values['cat'] = vote_cat

                elif self.request.get('stats_cat'):
                    owner_id = self.request.get('owner')
                    stats_cat = self.request.get('stats_cat')
                    #cat_id = cat_key(owner_id, stats_cat)
                    
                    results, unvoted = listResult(owner_id, stats_cat, user_id)
                    results_sorted = sorted(results.items(), key=lambda x: x[1][2], reverse=True)
                    template_values['results'] = results_sorted
                    template_values['unvoted'] = unvoted
    
                elif self.request.get('stats')=='all':
                    query = {}
                    list = searchCat(query)
                    
                    template_values['stats_cat'] = list.run()
    
                elif self.request.get('upload_failure'):
                    template_values['upload_failure'] = True


        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
                
        
        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))


app = webapp2.WSGIApplication([('/', Dispatcher), ('/addCat', AddCat), ('/addItem', AddItem), ('/vote', VoteItem), ('/import', ImportCat), ('/export', ExportHandler), ('/export/([^/]+)?', ExportCat), ('/addComment', AddComment)], debug=True)