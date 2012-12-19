from __future__ import with_statement
import cgi
import datetime
import urllib
import os
import random
import operator
import pickle
import webapp2
import test

from google.appengine.api import users
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import files
from google.appengine.ext.db import stats
from google.appengine.api import memcache

import jinja2
import xml.dom.minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement, Comment
from model import *

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


#get random items under the category
def pickRandom(cat_id):
    num = Item.all().ancestor(cat_id).count()
    rand = random.randint(0, num-1)
    item = Item.get_by_key_name(str(rand), parent=cat_id)
    return item

#list all voting results under the category
def listResult(owner_id, cat_name, user_id):
    results = {}
    not_voted = {}
    cat_id = cat_key(owner_id, cat_name)
    query = {'ancestor':cat_id}
    items = searchItem(query).run()
    for item in items:
        item_id = item_key(owner_id + '/' + cat_name, item.name)
        un_item = searchItem
        q_favored = {'ancestor' : item_id}
        favored_count = searchVote(q_favored).count()
        q_un = {'unvoted_item' : item}
        un_count = searchVote(q_un).count()
        
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
        expiration_time = self.request.get('expiration_time')
        
        if users.get_current_user():
            user_id = users.get_current_user().user_id()
            user_name = users.get_current_user().nickname()
            query = {'ancestor':user_key(user_id), 'name':cat_name}
            if searchCat(query).count() == 0:
                cat = insertCat(user_id, user_name, cat_name, expiration_time)
                #self.response.out.write(cat_id)
                self.redirect('/category?id='+user_id+'&name'+cat_name+'&add=success')
            #self.redirect('/?add=success&cat_name=' + cat_name + '&owner=' + user_id)
            else:
                self.redirect('/category?id='+user_id+'&add=fail')

class AddItem(webapp2.RequestHandler):
    def post(self):
        template_values = {}
        user_id = users.get_current_user().user_id()
        #self.response.out.write(user_id)
        cat_name = self.request.get('cat_name')
        #self.response.out.write(cat_name)
        owner_id = self.request.get('owner')
        if owner_id == user_id:
            cat_id = cat_key(owner_id, cat_name)
            item_name = self.request.get('item_name')
            pic_dir = self.request.get('picture')
            
            if item_name:
                query = {'ancestor': cat_id, 'name': item_name}
                list = searchItem(query)
                num = list.count()
                if num == 0:
                    item = insertItem(cat_id, item_name, pic_dir, str(num))
                    #self.response.out.write(item.name)
                    
                    self.redirect('/category?id='+user_id+'&name='+cat_name)
            #self.redirect('/?' + urllib.urlencode({'parent': cat_name}) + '&' + urllib.urlencode({'owner':user_id}) + '&'+ urllib.urlencode({'item_name': item_name}))
            else:
                
                self.redirect('/category?id='+user_id+'&name='+cat_name+'&add_fail=True')

class Image(webapp2.RequestHandler):
    def get(self):
        item = db.get(self.request.get('img_id'))
        if item.picture:
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(item.picture)
        else:
            self.response.out.write('No image')

class VoteItem(webapp2.RequestHandler):
    def get(self):
        cat_name = self.request.get('category')
        owner_id = self.request.get('id')
        user_id = users.get_current_user().user_id()
        cat_id = owner_id + '/' + cat_name
        
        if self.request.get('item_name'):
            item_name = self.request.get('item_name')
            unvoted_item = self.request.get('unvote_item')
            item1_id = item_key(cat_id, item_name)
            query = {'ancestor':cat_key(owner_id, cat_name), 'name':unvoted_item}
            item2 = searchItem(query).get()
            vote1 = insertVote(user_id, item1_id, item2)
            #self.response.out.write(item_name)
            
            self.redirect('/next_vote?prev1=' + item_name + '&prev2=' + unvoted_item + '&category=' + cat_name + '&id=' + owner_id)
        

class ImportCat(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try:
            upload = self.get_uploads()[0]
            blob_key=upload.key()
            blob_reader = blobstore.BlobReader(blob_key)
            document = blob_reader.read()
            dom = xml.dom.minidom.parseString(document)
            cat_name = dom.getElementsByTagName("NAME")[0]
            user_id = users.get_current_user().user_id()
            user_name = users.get_current_user().nickname()
            
            name = getText(cat_name.childNodes)
            
            items = dom.getElementsByTagName("ITEM")
            
            query = {'ancestor':user_key(user_id), 'name':name}
            if searchCat(query).count() == 0:
                d = datetime.timedelta(days=+1)
                expiration_time = (datetime.datetime.now()+d).strftime("%m/%d/%Y")
                cat = insertCat(user_id, user_name, name, expiration_time)
                cat_id = cat_key(user_id, name)
                for item in items:
                    item_name = getText(item.getElementsByTagName("NAME")[0].childNodes)
                    query = {'ancestor': cat_id}
                    num = searchItem(query).count()
                    insertItem(cat_id, item_name, None, str(num))
                blob_reader.close()
                self.redirect('/category?upload=success&id='+user_id)
            
            else:
                modified = {}
                cat_id = cat_key(user_id, name)
                for item in items:
                    item_name = getText(item.getElementsByTagName("NAME")[0].childNodes)
                    query = {'ancestor':cat_id, 'name':item_name}
                    if searchItem(query).count() == 0:
                        query = {'ancestor': cat_id}
                        num = searchItem(query).count()
                        insertItem(cat_id, item_name, None, str(num))
                        modified[item_name] = 1
                    else:
                        modified[item_name] = 0
                
                query = {'ancestor':cat_id}
                list = searchItem(query)
                for l in list:
                    if not l.name in modified:
                        item_id = item_key(user_id+'/'+name, l.name)
                        q_vote = {'ancestor':item_id}
                        deleteVote(q_vote)
                        q_vote = {'unvoted_item': l}
                        deleteVote(q_vote)
                        q_comment = {'ancestor':item_id}
                        deleteComment(q_comment)
                        q_item = {'ancestor':cat_id, 'name':l.name}
                        deleteItem(q_item)
                
                blob_reader.close()
                self.redirect('/category?upload=success&id='+user_id)

        except:
            self.redirect('/category?upload=fail&id='+user_id)

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
            pic = SubElement(i, 'PICTURE')
            pic.text = pickle.dumps(item.picture)
        
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
            name = str(file_key)
            self.send_blob(file_key, save_as=name+'.xml')
#self.response.out.write(file_key)

class AddComment(webapp2.RequestHandler):
    def post(self):
        user_id = users.get_current_user().user_id()
        user_name = users.get_current_user().nickname()
        #self.response.out.write(user_id)
        cat_name = self.request.get('category')
        #self.response.out.write(cat_name)
        owner_id = self.request.get('id')
        item_name = self.request.get('name')
        #self.response.out.write(item_name)
        content = self.request.get('content')
        item_id = item_key(owner_id+'/'+cat_name, item_name)
        query = {'ancestor':item_id, 'commenter_id':user_id}
        if searchComment(query).count() == 0:
            insertComment(user_name, user_id, item_id, content)
            self.redirect('/item?add=success&name=' + item_name + '&category=' + cat_name + '&id=' + owner_id)
        else:
            self.redirect('/item?add=fail&name=' + item_name + '&category=' + cat_name + '&id=' + owner_id)

class RemoveItem(webapp2.RequestHandler):
    def post(self):
        user_id = users.get_current_user().user_id()
        cat_name = self.request.get('cat_name')
        owner_id = self.request.get('owner')
        item_name = self.request.get('item_name')
        item_id = item_key(owner_id+'/'+cat_name, item_name)
        cat_id = cat_key(owner_id, cat_name)
        q_vote = {'ancestor':item_id}
        deleteVote(q_vote)
        q_vote = {'unvoted_item': item_id}
        deleteVote(q_vote)
        q_comment = {'ancestor':item_id}
        deleteComment(q_comment)
        q_item = {'ancestor':cat_id, 'name':item_name}
        deleteItem(q_item)
        
        self.redirect('/category?name=' + cat_name + '&id=' + owner_id + '&remove=success')

class BaseHandler(webapp2.RequestHandler):
    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        
        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)
    
    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

class ViewCategory(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
    
        if not self.request.get('id'):
            query = {}
            list = memcache.get('cat_all')
            if list is None:
                list = searchCat(query)
                memcache.add('cat_all', list, 60)
            
            template_values['categories'] = list
        
        elif self.request.get('id'):
            id = self.request.get('id')
            if not self.request.get('name'):
                list = memcache.get('cat_'+id)
                if list is None:
                    query = {'ancestor' : user_key(id)}
                    list = searchCat(query)
                    memcache.add('cat_'+id, list, 60)
                
                template_values['categories'] = list
                template_values['view'] = False
                upload_url = blobstore.create_upload_url('/import')
                template_values['import'] = upload_url
            
            elif self.request.get('name'):
                name = self.request.get('name')
                list = memcache.get('cat_'+id+'_'+name)
                if list is None:
                    cat_id = cat_key(id, name)
                    query = {'ancestor' : cat_id}
                    list = searchItem(query)
                    memcache.add('cat_'+id+'_'+name, list, 60)
                
                template_values['items'] = list
                template_values['cat_name'] = name
                template_values['owner'] = id
                a = {}
                b = {}
                i = 0
                for item in list:
                    a[item.name] = i
                    i = i + 1
                    b[item.name] = item.key()
                template_values['id'] = a
                template_values['key'] = b

                if self.request.get('success'):
                    template_values['remove'] = 'success'
                            
        if self.request.get('add_fail'):
            template_values['add_fail'] = True
    
        if self.request.get('add') == 'success':
            template_values['add'] = 'success'
        elif self.request.get('add') == 'fail':
            template_values['add'] = 'fail'
        if self.request.get('not_enough'):
            template_values['not_enough'] = 0

        
        template_values['now'] = datetime.datetime.today()

        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

        #self.response.out.write(list)

class ViewItem(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
        
    
        item_name = self.request.get('name')
        cat_name = self.request.get('category')
        owner_id = self.request.get('id')            
        cat_id = cat_key(owner_id, cat_name)
        query = {'ancestor' : cat_id, 'name' : item_name}
        item = searchItem(query).get()
        item_id = item_key(owner_id+'/'+cat_name, item_name)
        q_comment = {'ancestor' : item_id}
        comments = searchComment(q_comment).run()
        
        template_values['item'] = item
        template_values['cat_name'] = cat_name
        template_values['owner'] = owner_id
        template_values['comments'] = comments
        template_values['item_key'] = item.key()        
                  
        if self.request.get('add') == 'fail':
            template_values['add'] = 'fail'
        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

class Search(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext

        query_name = self.request.get('name')
        q_cat = {'name':query_name}
        cat_list = searchCat(q_cat)
        q_item = {'name': query_name}
        item_list = searchItem(q_item)
        
        template_values['query_cat'] = cat_list
        template_values['query_item'] = item_list
        template_values['count_cat'] = cat_list.count()
        template_values['count_item'] = item_list.count()
        
        a = {}
        b = {}
        i = 0
        for item in item_list:
            a[item.name] = i
            i = i + 1
            b[item.name] = item.key()
        template_values['id'] = a
        template_values['key'] = b
        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

class NextVote(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext

        id = self.request.get('id')
        vote_cat = self.request.get('category')
        owner_id = self.request.get('id')
        cat_id = cat_key(owner_id, vote_cat)

        query={'ancestor':cat_id}
        count = searchItem(query).count()
        if count <= 2:
            self.redirect('/category?not_enough='+str(count))

        elif self.request.get('prev1'):
            prev1 = self.request.get('prev1')
            prev2 = self.request.get('prev2')
            template_values['prev1'] = prev1
            template_values['prev2'] = prev2
        #item1 = 'a'
        #item2 = 'b'
        
            item1 = pickRandom(cat_id)        
            while (not item1) or (item1 and item1.name == prev1):
                item1 = pickRandom(cat_id)        
            item2 = pickRandom(cat_id)        
            while (not item2) or (item2 and item2.name == item1.name) or (item2 and item2.name == prev1):
                item2 = pickRandom(cat_id)
                
        else:
            item1 = pickRandom(cat_id)
            item2 = pickRandom(cat_id)            
            while not item1:
                item1 = pickRandom(cat_id)            
            while (not item2) or (item2 and item2.name == item1.name):
                item2 = pickRandom(cat_id)
                
        if count > 2:
            template_values['vote'] = []            
            template_values['vote'] = [item1, item2]
            template_values['vote_key'] = [item2.key(), item1.key()]
        template_values['owner'] = owner_id
        template_values['cat'] = vote_cat

        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

class Skip(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
                
        id = self.request.get('id')
        vote_cat = self.request.get('category')
        owner_id = self.request.get('id')
        cat_id = cat_key(owner_id, vote_cat)
        query={'ancestor':cat_id}
        count = searchItem(query).count()
        if count <= 2:
            self.redirect('/category?not_enough='+str(count))
        else:
            not_skip = self.request.get('not_skip')
            skip_item = self.request.get('skip_item')
            query = {'ancestor' : cat_id, 'name' : self.request.get('item')}
            item1 = searchItem(query).get()
            #self.response.out.write(item1)            
            item2 = pickRandom(cat_id)
            while (not item2) or (item2 and item2.name == item1.name) or (item2.name == skip_item):
                item2 = pickRandom(cat_id)
            
            template_values['vote'] = []
            if not_skip == '1':
                template_values['vote'] = [item1, item2]
                template_values['vote_key'] = [item1.key(), item2.key()]
            else:
                template_values['vote'] = [item2, item1]
                template_values['vote_key'] = [item2.key(), item1.key()]
        template_values['owner'] = owner_id
        template_values['cat'] = vote_cat
        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

class StatCat(webapp2.RequestHandler):
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
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''
        template_values['url'] = url
        template_values['url_linktext'] = url_linktext
                
        owner_id = self.request.get('id')
        stats_cat = self.request.get('name')
        #cat_id = cat_key(owner_id, stats_cat)
        
        results, unvoted = listResult(owner_id, stats_cat, user_id)
        results_sorted = sorted(results.items(), key=lambda x: x[1][2], reverse=True)
        template_values['results'] = results_sorted
        template_values['unvoted'] = unvoted

        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

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
            if not memcache.get('username'):
                memcache.add('username', username, 3600)
                memcache.add('user_id', user_id, 3600)
            else:
                memcache.get('username')
                memcache.get('user_id')
        
            if not self.request.arguments():
                template_values['home'] = True
        
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            username = ''

        template_values['url'] = url
        template_values['url_linktext'] = url_linktext


        template = jinja_environment.get_template('view/index.html')
        self.response.out.write(template.render(template_values))

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'my-super-secret-key',
}
app = webapp2.WSGIApplication([('/', Dispatcher), ('/addCat', AddCat), ('/addItem', AddItem), ('/vote', VoteItem), ('/import', ImportCat), ('/export', ExportHandler), ('/export/([^/]+)?', ExportCat), ('/addComment', AddComment), ('/removeItem', RemoveItem), ('/img', Image), ('/search', Search), ('/category', ViewCategory), ('/item', ViewItem), ('/next_vote', NextVote), ('/skip', Skip), ('/stats_cat', StatCat)], debug=True, config=config)