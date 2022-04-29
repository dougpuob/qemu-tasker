# Python Remote Control library (pyrc)


``` text
      Server:1                                       Client:*
 ┌────────────────┐                             ┌────────────────┐
 │                │         TCP connection      │                │
 │                │◄----------------------------│                │
 │    pyrc.py     │                             │    pyrc.py     │
 │                │           Execute           │                │
 │                │           List              │                │
 │                │           Upload            │                │
 │                │           Download          │                │
 │                │◄---------------------------►│                │
 └────────────────┘                             └────────────────┘
```


## Features
1. Supported three major operating systems, `Windows`, `Linux`, `macOS`.
2. Supported four major functions, `Execute`, `List`, `Update`, and `Download`.


## Server
``` python
def thread_routine(server: rcserver):
    if server:
        server.start()

if __name__ == '__main__':
    server = rcserver(_HOST_, _PORT_, debug_enabled=True)
    thread = threading.Thread(target=thread_routine, args=(server,))
    thread.daemon = True
    thread.start()
```


## Client
``` python
if __name__ == '__main__':
    client = rcclient()
    if client.connect(_HOST_, _PORT_):
        result: rcresult = client.execute('ls')
        result: rcresult = client.upload('id_rsa.pub', '~/.ssh')
        result: rcresult = client.download('~/.ssh/id_rsa.pub', '.')
        result: rcresult = client.list('.')
```

## Header format

```
   +--------------------------------------------------------------+
   |           Header              |            Payload           |
   0         1         2       3   |          (data+chunk)        |
   0123456789012345678900123...|...|..............................|
   |a     ||  ||  |                |              |               |
   ^^^^^^^^|b ||  |                | payload_data | payload_chunk |
           ^^^^|c |                |d             |e              |
               ^^^^                |^^^^^^^^^^^^^^|^^^^^^^^^^^^^^^|

   a: signature     [00:07]
   b: header_size   [08:11]
   c: total_size    [12:15]
   d: payload_data  [payload:length_payload_data]
   e: payload_chunk [payload+length_payload_chunk:total_size]

```

## Handsharks

```
Command     Client      Server
===============================
upload      ask   --->
            data  --->
            done  --->
                  <---  done
-------------------------------
download    ask   --->
                  <---  data
                  <---  done?
-------------------------------
list        ask   --->
                  <---  data?
                  <---  done
-------------------------------
execute     ask   --->
                  <---  data
                  <---  done?
-------------------------------

```


## Execute

```

class execute_subcmd(Enum):
    unknown = 0
    start = 1
    query = 2
    kill = 3

```


## License
Apache
