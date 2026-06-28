from pybatfish.client.session import Session

bf = Session(host="host.docker.internal")

try:
    bf.list_networks()
    print("Hey from Batfish")
    print("✔ Batfish reachable")
except Exception as e:
    print("✖ Batfish not reachable")
    print(e)
