# app.py

import os
import base64

import uvicorn
from starlette_wtf import StarletteForm
from starlette.responses import HTMLResponse
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
from typing import Optional, Any

from pydantic import BaseSettings, BaseModel, AnyUrl, Field

from fastapi import Request, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from wtforms import URLField, SelectField, BooleanField

import logging

from annotator import CSV_Annotator

class Settings(BaseSettings):
    app_name: str = "CSVtoCSVW"
    admin_email: str = os.environ.get("ADMIN_MAIL") or "csvtocsvw@matolab.org"
    items_per_user: int = 50
    version: str = "v1.1.3"
    config_name: str = os.environ.get("APP_MODE") or "development"
    openapi_url: str ="/api/openapi.json"
    docs_url: str = "/api/docs"
settings = Settings()

#flash integration flike flask flash
def flash(request: Request, message: Any, category: str = "info") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request):
    print(request.session)
    return request.session.pop("_messages") if "_messages" in request.session else []

middleware = [Middleware(SessionMiddleware, secret_key='super-secret')]
app = FastAPI(
    title="CSVtoCSVW",
    description="Generates JSON-LD for various types of CSVs, it adopts the Vocabulary provided by w3c at CSVW to describe structure and information within. Also uses QUDT units ontology to lookup and describe units.",
    version=settings.version,
    contact={"name": "Thomas Hanke, Mat-O-Lab", "url": "https://github.com/Mat-O-Lab", "email": settings.admin_email},
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_url=settings.openapi_url,
    docs_url=settings.docs_url,
    redoc_url=None,
    middleware=middleware
)
app.add_middleware(
CORSMiddleware,
allow_origins=["*"], # Allows all origins
allow_credentials=True,
allow_methods=["*"], # Allows all methods
allow_headers=["*"], # Allows all headers
)
app.add_middleware(uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware, trusted_hosts="*")

app.mount("/static/", StaticFiles(directory='static', html=True), name="static")
templates= Jinja2Templates(directory="templates")
templates.env.globals['get_flashed_messages'] = get_flashed_messages
# bootstrap = Bootstrap(app)

logging.basicConfig(level=logging.DEBUG)

separators = ["auto", ";", ",", "\\t", "\\t+",
              "|", ":", "\s+", "\s+|\\t+|\s+\\t+|\\t+\s+"]
encodings = ['auto', 'ISO-8859-1', 'UTF-8', 'ascii', 'latin-1', 'cp273']

class AnnotateRequest(BaseModel):
    data_url: AnyUrl = Field('', title='Raw CSV Url', description='Url to raw csv')
    separator: Optional[str] = Field('auto', title='Table Column Separator', description='Column separator of the data table part.',omit_default=True)
    header_separator: Optional[str] = Field('auto', title='Additional Header Column Separator', description='Column separator of additional header that might occure before the data table.',omit_default=True)
    encoding: Optional[str] = Field('auto', title='Encoding', description='Encoding of the file',omit_default=True)
    include_table_data: Optional[bool] = Field(False, title='Include Table Data', description='If to include the also the table data.',omit_default=True)
    class Config:
        schema_extra = {
            "example": {
                "data_url": "https://github.com/Mat-O-Lab/CSVToCSVW/raw/main/examples/example.csv",
                "separator": "auto",
                "header_separator": "auto",
                "encoding": 'auto',
                "include_table_data": False
            }
        }
class AnnotateResponse(BaseModel):
    filename:  str = Field('example-metadata.json', title='Resulting File Name', description='Suggested filename of the generated json-ld')
    filedata: str = Field('', title='Generated JSON-LD', description='The generated jdon-ld for the given raw csv file as string in utf-8.')


class StartForm(StarletteForm):
    data_url = URLField(
        'URL Data File',
        #validators=[DataRequired()],
        description='Paste URL to a data file, e.g. csv, TRA',
        render_kw={"placeholder": "https://github.com/Mat-O-Lab/CSVToCSVW/raw/main/examples/example.csv"},
    )
    separator_sel = SelectField(
        'Choose Data Table Separator, default: auto detect',
        choices=separators,
        description='select a separator for your data table manually',
        default='auto'
        )
    header_separator_sel = SelectField(
        'Choose Additional Header Separator, default: auto detect',
        choices=separators,
        description='select a separator for the additional header manually',
        default='auto'
        )
    encoding_sel = SelectField(
        'Choose Encoding, default: auto detect',
        choices=encodings,
        description='select an encoding for your data manually',
        default='auto'
        )
    include_table_data = BooleanField(
        'Include Table Data',
        description='Should the table data be included?',
        default=''
        )

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """GET /: form handler
    """
    start_form = await StartForm.from_formdata(request)
    result = ''
    return templates.TemplateResponse("index.html",
        {"request": request,
        "start_form": start_form,
        "result": result
        }
    )

@app.post("/", response_class=HTMLResponse)
async def index(request: Request):
    """POST /: form handler
    """
    start_form = await StartForm.from_formdata(request)
    result = ''
    if await start_form.validate_on_submit():
        annotator = CSV_Annotator(
            separator=start_form.separator_sel.data,
            header_separator=start_form.header_separator_sel.data,
            encoding=start_form.encoding_sel.data,
            include_table_data=start_form.include_table_data.data
        )
        if not start_form.data_url.data:
            start_form.data_url.data=start_form.data_url.render_kw['placeholder']
            flash(request,'URL Data File empty: using placeholder value for demonstration','info')
        try:
            meta_file_name, result = annotator.process(
                start_form.data_url.data)
        except (ValueError, TypeError) as error:
            flash(request,str(error),'error')
        else:
            b64 = base64.b64encode(result.encode())
            payload = b64.decode()
        return templates.TemplateResponse("index.html",
            {"request": request,
            "start_form": start_form,
            "result": result,
            "payload": payload,
            "filename": meta_file_name  
            }
        )
    return templates.TemplateResponse("index.html",
        {"request": request,
        "start_form": start_form,
        "result": result
        }
    )


@app.post("/api", response_model=AnnotateResponse)
async def api(annotate: AnnotateRequest) -> dict:
    annotator = CSV_Annotator(
        annotate.encoding, annotate.separator, annotate.header_separator, annotate.include_table_data)
    filename, file_data = annotator.process(annotate.data_url)
    return {"filename": filename, "filedata": file_data}


@app.get("/info", response_model=Settings)
async def info() -> dict:
    return settings

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app_mode=os.environ.get("APP_MODE") or 'production'
    if app_mode=='development':
        reload=True
        access_log=True
    else:
        reload=False
        access_log=False
    uvicorn.run("app:app",host="0.0.0.0",port=port, reload=reload, access_log=access_log)