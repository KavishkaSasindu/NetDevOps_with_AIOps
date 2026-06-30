from pybatfish.client.session import Session

bf = Session(host="172.23.71.245",port="9996")

try:
    bf.list_networks()
<<<<<<< HEAD
    print("Hey from Batfish Server....wq
")
=======
    print("Hey from Batfish Server.....")
>>>>>>> 70ad60b (updated test python file)
    print("✔ Batfish reachable")
except Exception as e:
    # Error Logging
    print("✖ Batfish not reachable")
    print(e)
