import operator
import socket
import os
import pickle
import time
import threading
from queue import Queue
import urllib.parse

class InTransitObject():
    def __init__(self, obj, count, req=False):
        self.obj = obj
        self.time = time.time()
        self.count = count

class SyncObject():
    def __init__(self, sync_location, sync_location2):
        self.que = Queue()
        self.rec = Queue()
        self.sync_location = sync_location
        self.count = 0

        dws = threading.Thread(target=self.downstream, args=(sync_location2,self.que,self.rec))
        dws.start()

    def start(self, obj):
        obj = InTransitObject(obj, self.count)
        self.que.put(obj)
        self.count += 1
    
    def upstream(self, sync_location, queue):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            sock.connect(sync_location)
        except socket.error as msg:
            print(msg)

        write = sock.makefile('w')

        try:
            while True:
                msg = queue.get()
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

    def start_send(self):
        ups = threading.Thread(target=self.upstream, args=(self.sync_location,self.que,))
        ups.start()

class SyncListAction():
    def __init__(self, action, args):
        self.action = action
        self.args = args

class SyncList(SyncObject):
    def __init__(self, sync_location, sync_location2):
        super().__init__(sync_location, sync_location2)
        self.compiled = []
        self.ack_count = -1

    def __str__(self) -> str:
        return f"[{', '.join(str(e) for e in self.render())}]"

    def append(self, obj):
        self.rec.put(InTransitObject(SyncListAction("append", [obj])))
        self.send_obj(SyncListAction("append", [obj]))

    def insert(self, obj, position):
        self.rec.put(InTransitObject(SyncListAction("insert", [obj, position])))
        self.send_obj(SyncListAction("insert", [obj, position]))
    
    def remove(self, obj, position):
        self.rec.put(InTransitObject(SyncListAction("remove", [obj, position])))
        self.send_obj(SyncListAction("remove", [obj, position]))

    def pop(self):
        self.rec.put(InTransitObject(SyncListAction("pop", []), 0))
        self.send_obj(SyncListAction("pop", []))

    def render(self):
        c = self.compiled
        stopnext = False
        rec = list(self.rec.queue)
        with self.rec.mutex:
            self.rec.queue.clear()
        rec.sort(key=operator.attrgetter('time'))

        f = 0
        for action in rec:
            f += 1
            if action.count == self.ack_count+1:
                self.ack_count += 1
            else:
                stopnext = True
            if action.obj.action == "append":
                self.compiled.append(action.obj.args[0])
            elif action.obj.action == "insert":
                self.compiled.insert(action.obj.args[0], action.obj.args[1])
            elif action.obj.action == "pop":
                self.compiled.pop()
            elif action.obj.action == "remove":
                self.compiled.insert(action.obj.args[0], action.obj.args[1])
            if stopnext == True:
                break

        rec = rec[f:]
        for action in rec:
            if action.obj.action == "append":
                c.append(action.obj.args[0])
            elif action.obj.action == "insert":
                c.insert(action.obj.args[0], action.obj.args[1])
            elif action.obj.action == "pop":
                c.pop()
            elif action.obj.action == "remove":
                c.insert(action.obj.args[0], action.obj.args[1])

        return c
