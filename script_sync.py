import operator
import socket
import os
import pickle
import time
import threading
from queue import Queue
import urllib.parse

END_STR = ".í Î¢0«u.@tQ..ºª;¨M6Ï.æ.VýMµ.¤Ó.²...ü×¤(;ÿ.6:.*J .ÄdÀ	&¨z.ï.y¹q¥"

class InTransitObject():
    def __init__(self, obj):
        self.obj = obj
        self.time = time.time()
        self.uncompiled = False

class SyncObject():
    def __init__(self, up_location, down_location):
        self.que = Queue()
        self.rec = Queue()
        self.up_location = up_location
        self.connected = False

        self.dws = threading.Thread(target=self.downstream, args=(down_location,self.que,self.rec))
        self.dws.start()

    def send_obj(self, obj):
        obj = InTransitObject(obj)
        self.que.put(obj)

    def upstream(self, up_location, queue):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.connect(up_location)
        except socket.error as msg:
            print(msg)

        write = sock.makefile('w')

        try:
            while True:
                msg = queue.get()
                if msg == END_STR:
                    break
                write.write(urllib.parse.quote_from_bytes(pickle.dumps(msg)) + '\n')
                write.flush()
        finally:
            sock.close()
        
    def downstream(self, sync_location, queue, ret):
        try:
            os.unlink(sync_location)
        except OSError:
            if os.path.exists(sync_location):
                raise

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(sync_location)

        sock.listen(1)

        connection, client_address = sock.accept()

        read  = connection.makefile('r')
        write = connection.makefile('w')
        try:
            while True:
                data = urllib.parse.unquote_to_bytes(read.readline())
                ret.put(pickle.loads(data))
        finally:
            connection.close()

    def start(self):
        self.connected = True
        self.ups = threading.Thread(target=self.upstream, args=(self.up_location,self.que,))
        self.ups.start()

class SyncListAction():
    def __init__(self, action, args):
        self.action = action
        self.args = args

class SList(SyncObject):
    def __init__(self, up_location, down_location):
        super().__init__(up_location, down_location)
        self.compiled = []
        self.compile_timer = 2/1000
        self.uncompiled = []

    def __str__(self) -> str:
        return f"[{', '.join(str(e) for e in self.render())}]"

    def __repr__(self) -> str:
        return f"[{', '.join(str(e) for e in self.render())}]"

    def __len__(self) -> int:
        return len(self.render())
    
    def __del__(self):
        try: 
            self.que.put(END_STR)
        except Exception:
            pass

    def __getitem__(self, i):
        return self.render()[i]

    def to_list(self):
        return self.render()

    def index(self, i):
        return self.render().index(i)

    def count(self, o):
        return self.render().count(o)

    def append(self, obj):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("append", [obj])))
        self.send_obj(SyncListAction("append", [obj]))

    def insert(self, obj, position):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("insert", [obj, position])))
        self.send_obj(SyncListAction("insert", [obj, position]))
    
    def remove(self, obj):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("remove", [obj])))
        self.send_obj(SyncListAction("remove", [obj]))

    def extend(self, obj):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("extend", [obj])))
        self.send_obj(SyncListAction("extend", [obj]))

    def pop(self):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("pop", [])))
        self.send_obj(SyncListAction("pop", []))

    def clear(self):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("clear", [])))
        self.send_obj(SyncListAction("clear", []))

    def reverse(self):
        if not self.connected:
            self.start()
        self.rec.put(InTransitObject(SyncListAction("reverse", [])))
        self.send_obj(SyncListAction("reverse", []))

    def render(self):
        if not self.connected:
            self.start()
        c = self.compiled[:]
        rec = list(self.rec.queue) + self.uncompiled
        with self.rec.mutex:
            self.rec.queue.clear()
        rec.sort(key=operator.attrgetter('time'))

        for action in rec:
            c = list_action(c, action)
            if time.time()-action.time < self.compile_timer and not action.uncompiled:
                action.uncompiled = True
                self.uncompiled.append(action)
            elif time.time()-action.time > self.compile_timer and action.uncompiled:
                self.uncompiled.remove(action)
                self.compiled = list_action(self.compiled, action)
            elif time.time()-action.time > self.compile_timer and not action.uncompiled:
                self.compiled = list_action(self.compiled, action)
        return c

def list_action(lst, act):
    if act.obj.action == "append":
        lst.append(act.obj.args[0])
    elif act.obj.action == "insert":
        lst.insert(act.obj.args[0], act.obj.args[1])
    elif act.obj.action == "pop":
        lst.pop()
    elif act.obj.action == "sort":
        lst.sort()
    elif act.obj.action == "reverse":
        lst.reverse()
    elif act.obj.action == "extend":
        lst.extend(act.obj.args[0])
    elif act.obj.action == "remove":
        lst.remove(act.obj.args[0])
    elif act.obj.action == "clear":
        lst.clear()
    return lst
