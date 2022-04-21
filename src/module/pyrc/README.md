# Python Remote Control (pyrc)

``` text
      Server:1                                       Client:*
 ┌────────────────┐                             ┌────────────────┐
 │                │    Establish a connection   │                │
 │                │◄----------------------------│                │
 │    pyrc.py     │                             │    pyrc.py     │
 │                │           Execute           │                │
 │                │           List              │                │
 │                │           Upload            │                │
 │                │           Download          │                │
 │                │◄---------------------------►│                │
 └────────────────┘                             └────────────────┘
```

## Server
``` python
def thread_routine(server: rcserver):
    if server:
        server.start()

if __name__ == '__main__':
    server = rcserver(_HOST_, _PORT_, debug_enabled=True)
    thread = threading.Thread(target=thread_routine, args=(server,))
    thread.setDaemon(True)
    thread.start()
```

## Client
``` python
if __name__ == '__main__':
    client = rcclient(_HOST_, _PORT_)
    if client.connect():
        result: rcresult = client.execute('ls')
        result: rcresult = client.upload('id_rsa.pub', '~/.ssh')
        result: rcresult = client.download('~/.ssh/id_rsa.pub', '.')
        result: rcresult = client.list('.')

