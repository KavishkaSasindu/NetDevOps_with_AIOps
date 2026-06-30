from pybatfish.client.session import Session

bf = Session(host="172.23.71.245", port="9996")

try:
    bf.list_networks()
    print("Hey from Batfish Server.....")
    print("Connection is established....")
    print("✔ Batfish reachable")

except Exception as e:
    # Error Logging
    print("✖ Batfish not reachable")
    print(e)
