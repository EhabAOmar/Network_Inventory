import threading
from napalm import get_network_driver
import queue
import re
import json

# End of Support (EOS) file, which contains static records for each product id EOS date. We can substitute this by using API for the vendor website.
EOS_file = open("templates/EOS.txt")
EOS_dict = json.load(EOS_file)

def get_EOS(PID):
    if PID in list(EOS_dict.keys()):
        return EOS_dict[PID]
    else:
        return ""


def network_inventory(username,password,devices,action):

    # Global queue for storing the data for all threads outputs
    global data_queue
    data_queue = queue.Queue()

    # List of IPs of the devices
    IPs_list = list(devices.keys())

    # List of vendors of the devices
    vendor_list = list(devices.values())

    # Devices information including IP, username, password to be used in NAPALM
    devices_info = [ {"hostname": IPs_list[i], "username":username,"password": password} for i in range(len(IPs_list))]

    # Maximum 5 threads to work simultaneously
    thread_num = 5

    device_count = len(devices)


    # Dividing the list of devices to groups for Threading
    if device_count < 5:
        device_per_thread = 1
    else:
        device_per_thread = (device_count//thread_num) + (device_count%thread_num)
    group1 = devices_info[0:device_per_thread]
    group2 = devices_info[(device_per_thread):(2*device_per_thread)]
    group3 = devices_info[(2*device_per_thread):(3*device_per_thread)]
    group4 = devices_info[(3*device_per_thread):(4*device_per_thread)]
    group5 = devices_info[(4*device_per_thread):(5*device_per_thread)]

    # Dividing the vendor list of devices for Threading
    vendor_list1 = vendor_list[0:device_per_thread]
    vendor_list2 = vendor_list[(device_per_thread):(2*device_per_thread)]
    vendor_list3 = vendor_list[(2*device_per_thread):(3*device_per_thread)]
    vendor_list4 = vendor_list[(3*device_per_thread):(4*device_per_thread)]
    vendor_list5 = vendor_list[(4*device_per_thread):(5*device_per_thread)]


    # Create new Threads
    thread1 = threading.Thread(target=thread_run, args=(vendor_list1,group1,action))
    thread2 = threading.Thread(target=thread_run, args=(vendor_list2,group2,action))
    thread3 = threading.Thread(target=thread_run, args=(vendor_list3,group3,action))
    thread4 = threading.Thread(target=thread_run, args=(vendor_list4,group4,action))
    thread5 = threading.Thread(target=thread_run, args=(vendor_list5,group5,action))


    # Start new Threads
    thread1.start()
    thread2.start()
    thread3.start()
    thread4.start()
    thread5.start()

    # Wait for the Threads to be completed
    thread1.join()
    thread2.join()
    thread3.join()
    thread4.join()
    thread5.join()


    # data will be returned in dictionary structure
    data = {}
    while not data_queue.empty():
        items = data_queue.get()

        if action == "inventory":
            if items[4] not in data.keys(): # To add only first Serial-Number to avoid duplication
                data[items[4]] = items[::]   # Key is Serial-Number, Value are all other data
        else:
            data[items[0]] = items[::]  # Key is IP-Address, Value are all other data
    return data


def thread_run(vendor_list,group,action):

    i = 0
    for device_info in group:

        # For Juniper devices, default device type is Juniper
        if vendor_list[i].lower() in ["junos","juniper",""]:
            # Need to configure the following on Juniper router to enable netconf
            ## configure
            ## set system services netconf ssh
            ## commit
            try:
                driver = get_network_driver("junos")
                device = driver(**device_info)
                device.open()

                facts = device.get_facts()  # Retrieve device facts

                # Device IP address
                device_IP = device_info['hostname']

                # Device name or hostname
                hostname = facts['hostname']

                # Device software version
                version = facts['os_version']

                # Device model
                device_model = facts['model']

                # To extract version and model only
                if action == "version":
                    data_queue.put([device_IP, hostname, "Juniper", device_model, version])

                # To extract all hardware inventory
                else:
                    # get device hardware inventory by command line
                    inventory = device.cli(["show chassis hardware | except builtin"], )["show chassis hardware | except builtin"]
                    inventory2 = device.cli(["show chassis hardware clei-models | except builtin"], )["show chassis hardware clei-models | except builtin"]
                    lines = inventory.splitlines()

                    # Extract Product_ID, Serial-Number, Product-Description and End-of-Support (EOS)
                    for item in lines:
                        if "Chassis" not in item.split():
                            #Product_ID = re.findall("\d{3}-\d{6}", item)
                            part_number = re.findall("\d{3}-\d{6}", item)
                            if part_number != []:
                                #Product_ID = Product_ID[0]
                                part_number = part_number[0]
                                Product_ID = get_juniper_Product_ID(part_number,inventory2)
                                item_list = item.split()
                                Product_ID_index = item_list.index(part_number)
                                Serial_Number = item_list[Product_ID_index+1]
                                item_Description = " ".join(item_list[Product_ID_index+2:])
                                EOS = get_EOS(Product_ID)
                            else:
                                continue
                        else:       # for the item is for the Chassis, extract inventory will be handeled differently
                            Product_ID = device_model
                            item_Description = "Chassis"
                            Serial_Number = facts['serial_number']
                            EOS = get_EOS(Product_ID)
                        data_queue.put([device_IP, hostname, "Juniper", Product_ID,Serial_Number,item_Description,EOS,device_model,version])



            except Exception as e:
                print(f"exception: {e}")

        elif vendor_list[i].lower() in ["cisco","cisco xe","ios xe"]:
            try:
                driver = get_network_driver("ios")
                device = driver(**device_info)
                device.open()

                facts = device.get_facts()  # Retrieve device facts

                # Device IP address
                device_IP = device_info['hostname']

                # Device name or hostname
                hostname = facts['hostname']

                # Device software version
                version = facts['os_version']

                # Device model
                device_model = facts['model']

                # To extract version and model only
                if action == "version":
                    data_queue.put([device_IP, hostname, "Cisco", device_model, version])

                # To extract all hardware inventory
                else:
                    # get device hardware inventory by command line
                    inventory = device.cli(["show inventory | exclude BUILT-IN"], )["show inventory | exclude BUILT-IN"]


                    lines = inventory.splitlines()

                    # Extract Product_ID, Serial-Number, Product-Description and End-of-Support (EOS)
                    for item in lines:

                        if item.find("DESCR") != -1:
                            item_Description = re.findall('DESCR:\s".*"', item)
                            if item_Description == []:
                                item_Description = ""
                            else:
                                item_Description = item_Description[0].replace("DESCR:","").strip()

                            continue

                        elif item.find("PID") != -1:
                            Product_ID = re.findall('PID:\s[A-z0-9-]+\s', item)

                            if Product_ID==[]:
                                Product_ID = ""
                            else:
                                Product_ID = Product_ID[0].replace("PID:","").strip()
                            Serial_Number = re.findall('SN:\s[A-z0-9]+', item)

                            if Serial_Number==[]:
                                Serial_Number = ""
                            else:
                                Serial_Number = Serial_Number[0].replace("SN:","").strip()
                            EOS = get_EOS(Product_ID)
                        else:
                            continue

                        if Serial_Number != "":
                            data_queue.put([device_IP, hostname, "Cisco", Product_ID, Serial_Number, item_Description, EOS,device_model, version])


            except Exception as e:
                print(f"exception: {e}")

        elif vendor_list[i].lower() in ["huawei","huawei vrp","huawei_vrp"]:
            try:
                driver = get_network_driver("huawei_vrp")
                device = driver(**device_info)
                device.open()

                facts = device.get_facts()  # Retrieve device facts

                # Device IP address
                device_IP = device_info['hostname']

                # Device name or hostname
                hostname = facts['hostname']

                # Device software version
                version = facts['os_version']

                # Device model
                device_model = facts['model']

                # To extract version and model only
                if action == "version":
                    data_queue.put([device_IP, hostname, "Huawei", device_model, version])

                # To extract all hardware inventory
                else:
                    # get device hardware inventory by command line
                    inventory = device.cli(["display elabel"], )["display elabel"]


                    lines = inventory.splitlines()
                    Serial_Number = ""
                    Product_ID = ""
                    item_Description = ""

                    # Extract Product_ID, Serial-Number, Product-Description and End-of-Support (EOS)
                    for item in lines:
                        if item.find("BoardType") != -1:
                            Product_ID = item.replace("BoardType=","").strip()
                            EOS = get_EOS(Product_ID)
                            continue

                        elif item.find("BarCode") != -1:
                            Serial_Number = item.replace("BarCode=","").strip()
                            continue

                        elif item.find("Description") != -1:
                            item_Description = item.replace("Description=", "").strip()

                        if Serial_Number != "":
                            data_queue.put([device_IP, hostname, "Huawei", Product_ID, Serial_Number, item_Description, EOS,device_model, version])


            except Exception as e:
                print(f"exception: {e}")



        i = +1



def get_juniper_Product_ID(part_number,inventory):
    for item in inventory.splitlines():
        if part_number in item:
            item_list = item.split()
            Product_ID = item_list[-1]
            return Product_ID
    return part_number
