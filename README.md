
== Example ==
    
    import bbtornado.main
    
    from bbtornado.web import Application
    from bbtornado.models import Base, BaseModel
    from bbtornado.handlers import BaseHandler
    
    from sqlalchemy import Column, types
    
    class User(Base, BaseModel):
        __tablename__ = 'users'
        id = Column(types.Integer, primary_key=True, autoincrement=True)
        visits = Column(types.Integer, default=0)
    
    class MainHandler(BaseHandler):
        def get(self):
            if self.current_user == None:
                user = User()
                self.db.add(user)
                self.db.commit()
                print('created user', user.id)
                self.current_user = user.id
            else:
                user = self.db.query(User).get(self.current_user)
            self.write("Hello %s!  You've been here %s times before!" % (user.id, user.visits))
            user.visits += 1
            self.db.add(user)
            self.db.commit()
            self.finish()
    
    if __name__ == '__main__':
        bbtornado.main.setup()
        app = Application([
            (r"/", MainHandler)
        ])
        bbtornado.main.main(app)
