from pybatfish.client.session import Session

bf = Session(host="localhost")

try:
    bf.list_networks()
    print("✔ Batfish reachable")
except Exception as e:
    print("✖ Batfish not reachable")
    print(e)
