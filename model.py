from google.appengine.ext import db

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
    create_time = db.DateTimeProperty(auto_now_add=True)
    picture = db.BlobProperty()

#vote has ancestor item
class Vote(db.Model):
    voter = db.StringProperty()
    unvoted_item = db.ReferenceProperty()
    #favored = db.BooleanProperty()
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
def insertCat(user_id, user_name, cat_name, expiration_time):
    ancestor = user_key(user_id)
    time_str = expiration_time.split('/')
    cat_expt = datetime.datetime(int(time_str[2]), int(time_str[0]), int(time_str[1]), 1)
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
def insertItem(cat_id, item_name, pic_dir, key_name):
    randnum = random.random()
    item = Item(parent=cat_id, key_name=key_name, name=item_name, rand=randnum)
    if pic_dir:
        item.picture = db.Blob(pic_dir)
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
def insertVote(voter, voted_item_id, unvoted_item):
    vote = Vote(parent=voted_item_id, unvoted_item=unvoted_item, voter=voter)
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
def deleteVote(query):
    list = searchVote(query)
    if list.count() > 0:
        db.delete(list)

#remove all comments given the item
def deleteComment(query):
    list = searchComment(query)
    db.delete(list)

#remove the item give id
def deleteItem(query):
    list = searchItem(query)
    db.delete(list)

#remove the category given category id
def deleteCategory(query):
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