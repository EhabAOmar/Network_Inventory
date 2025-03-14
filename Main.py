from fastapi import FastAPI, Form, Request, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from utils import network_inventory
from datetime import datetime
import pandas as pd
import shutil
import os


app = FastAPI()

# Mount the static folder for CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates (HTML rendering)
templates = Jinja2Templates(directory="templates")



# Route to serve the user form (HTML page)
@app.get("/")
async def show_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

UPLOAD_DIR = "uploads"  # Directory to store uploaded files
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Create folder if it doesn't exist


@app.post("/inventory/")
async def process_form(
    request: Request,
    action: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    file: UploadFile = File(...)
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    if (not file.filename.endswith(".csv") and not file.filename.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Only CSV & XLSX files are allowed!")

    # Save the file under "uploads" folder
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if file.filename.endswith(".csv"):
        # Extracting the data from the .CSV file
        with open(file_location) as devices_list:
            lines = devices_list.readlines()

        # Delete the uploaded file after extracting devices information from it
        os.remove(file_location)

        # getting a dictionary contains the devices list in (IP-address:vendor) format
        try:
            devices = {line.split(",")[0].strip():line.split(",")[1].strip() for line in lines}
        except:
            raise HTTPException(status_code=500, detail="File Format Error --- Please be sure to write the format <ip-address>,<vendor> in the .csv file ---")

    else:
        pd_read = pd.read_excel(file_location, header=None).to_dict()


        devices = {pd_read[0][i]:pd_read[1][i] for i in range(len(pd_read.get(0)))}
        # Delete the uploaded file after extracting devices information from it
        os.remove(file_location)

    # Getting inventory from the devices
    global data
    data = network_inventory(username,password,devices,action)

    # Store data in session (or use query parameters)
    return templates.TemplateResponse("result.html", {"request": request, "data": data, "table_type": action})


@app.get("/download/{table_type}")
async def download_excel(table_type: str):

    sheet = {}

    if table_type == "version":
        IP_list, hostname_list, vendor_list, model_list, version_list = [], [], [], [], []
        data_list = list(data.values())
        for item in data_list:
            IP_list.append(item[0])
            hostname_list.append(item[1])
            vendor_list.append(item[2])
            model_list.append(item[3])
            version_list.append(item[4])

        sheet["Device IP"] = IP_list
        sheet["Hostname"] = hostname_list
        sheet["Vendor"] = vendor_list
        sheet["Model"] = model_list
        sheet["Version"] = version_list

    elif table_type == "inventory":
        IP_list, hostname_list, vendor_list, Product_ID_list, Serial_number_list, Product_Description_list, EOS_list, model_list, version_list = [], [], [], [], [], [], [], [], []
        data_list = list(data.values())
        for item in data_list:
            IP_list.append(item[0])
            hostname_list.append(item[1])
            vendor_list.append(item[2])
            Product_ID_list.append(item[3])
            Serial_number_list.append(item[4])
            Product_Description_list.append(item[5])
            EOS_list.append(item[6])
            model_list.append(item[7])
            version_list.append(item[8])

        sheet["Device IP"] = IP_list
        sheet["Hostname"] = hostname_list
        sheet["Vendor"] = vendor_list
        sheet["Product ID"] = Product_ID_list
        sheet["Serial Number"] = Serial_number_list
        sheet["Product Description"] = Product_Description_list
        sheet["EOS"] = EOS_list
        sheet["Model"] = model_list
        sheet["Version"] = version_list

    else:
        return {"error": "Invalid table type"}

    # Convert dictionary to DataFrame
    df = pd.DataFrame(sheet)

    # Get the current date to tag it to the output file
    date = datetime.today().strftime("%d-%m-%Y")

    # Save DataFrame to an Excel file
    file_path = f"{table_type}_data_{date}.xlsx"
    df.to_excel(file_path, index=False)

    # Serve the file for download
    return FileResponse(file_path, filename=file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


TEMPLATE_PATH = "templates/template.xlsx"

@app.get("/download-template")
async def download_template():
    if os.path.exists(TEMPLATE_PATH):
        return FileResponse(TEMPLATE_PATH, filename="template.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return {"error": "File not found"}


# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)