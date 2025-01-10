from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ory_kratos_client import ApiClient, Configuration, FrontendApi
from ory_kratos_client.models.update_registration_flow_with_password_method import UpdateRegistrationFlowWithPasswordMethod
from ory_kratos_client.models.update_registration_flow_body import UpdateRegistrationFlowBody
from ory_kratos_client.models.update_login_flow_with_password_method import UpdateLoginFlowWithPasswordMethod
from ory_kratos_client.models.update_login_flow_body import UpdateLoginFlowBody
from ory_kratos_client.exceptions import ApiException
import httpx
# from http.cookies import SimpleCookie
# from fastapi.middleware.cors import CORSMiddleware
# from ory_kratos_client.models import (
#     ContinueWithRecoveryUi,
#     ContinueWithSetOrySessionToken,
#     ContinueWithSettingsUi,
#     ContinueWithVerificationUi,
# )
# from ory_kratos_client.models import (
#     SuccessfulNativeRegistration,
#     SuccessfulNativeLogin
#     # UpdateRegistrationFlowBody,
#     # UpdateRegistrationFlowWithPasswordMethod,
#     # ContinueWith,
#     # Identity,
#     # Session,
# )
import requests


app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configure Ory Kratos client
config = Configuration(host="http://127.0.0.1:4433")
api_client=ApiClient(config)
# Set headers for the API client
api_client.set_default_header("Accept", "application/json")
api_client.set_default_header("Content-Type", "application/json")
frontend_api = FrontendApi(api_client)

# Home route


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Or specify allowed origins
#     allow_credentials=True,  # Allow credentials (cookies)
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # Kratos variables for the application
KRATOS_EXTERNAL_API_URL ="http://127.0.0.1:4433"

KRATOS_UI_URL ="http://127.0.0.1:8000"

# # Keto
KETO_API_READ_URL = "http://127.0.0.1:4466"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Check if the session cookie is present
    if "ory_kratos_session" not in request.cookies:
        return RedirectResponse(url=KRATOS_UI_URL)
    print(f"request.cookies: {request.cookies}")
    
   
    # Verify the session with Kratos
    response = requests.get(
        f"{KRATOS_EXTERNAL_API_URL}/sessions/whoami", cookies=request.cookies
    )
    
    kratos_response = response.json()
    print(f"Kratos response: {kratos_response}")
    print(f"Kratos status code: {response.status_code}")
    if response.status_code != 200 or not response.json().get("active"):
        raise HTTPException(status_code=403, detail="Forbidden")

   # Parse the JSON response
    

    if response.status_code != 200 or not kratos_response.get("active"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Extract the user's email from the session
    email = kratos_response.get("identity", {}).get("traits", {}).get("email")
    last = kratos_response.get("identity", {}).get("traits", {}).get("name", {}).get("last")
    first = kratos_response.get("identity", {}).get("traits", {}).get("name", {}).get("first")
    print(f"kratos email: {email}")
    print(f"kratos username: {first} {last}")

    # Check if the user has admin permissions via Keto
    permissions_response = requests.get(
        f"{KETO_API_READ_URL}/relation-tuples/check",
        params={
            "namespace": "app",
            "object": "dashboard",
            "relation": "read",
            "subject_id": email,
        }
    ) 
    
    # Log the raw Keto response text
    print(f"Raw Keto response text: {permissions_response.text}")
    print(f"Keto status code: {permissions_response.status_code}")

    if not permissions_response.json().get("allowed"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Render the dashboard template with the user's email
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": f"{first} {last}"})

# Login route

@app.get("/login")
async def show_login_form(request: Request):
    """
    Handles GET requests to display the login form.
    Fetches login flow data from Kratos.
    """
     # Check if the session cookie is present and valid
    if "ory_kratos_session" in request.cookies:
        session_response = requests.get(
            f"{KRATOS_EXTERNAL_API_URL}/sessions/whoami",
            cookies=request.cookies
        )
        if session_response.status_code == 200 and session_response.json().get("active"):
            return RedirectResponse(url="/dashboard")
    try:
        async with httpx.AsyncClient() as client:
            cookies = request.cookies
            headers = {"Accept": "application/json"}

            response = await client.get(
                "http://127.0.0.1:4433/self-service/login/browser",
                cookies=cookies,
                headers=headers,
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch login flow")
            
            print(f"response login: {response.json()}")

            flow_data = response.json()
            csrf_token = None

            # Extract CSRF token
            for node in flow_data["ui"]["nodes"]:
                attributes = node["attributes"]
                if attributes.get("name") == "csrf_token":
                    csrf_token = attributes["value"]
                    break

            if not csrf_token or not flow_data["id"]:
                raise HTTPException(status_code=400, detail="CSRF token or Flow ID is missing.")

            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "flow_id": flow_data["id"],
                    "csrf_token": csrf_token,
                },
            )
    except Exception as e:
        print(f"Error fetching login flow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/login")
async def handle_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    flow: str = Form(...),
    csrf_token: str = Form(...),
):
    """
    Handles POST requests for user login.
    """
    try:
        # Prepare the login data
        login_data = UpdateLoginFlowBody(
            actual_instance=UpdateLoginFlowWithPasswordMethod(
                csrf_token=csrf_token,
                password=password,
                method="password",
                identifier=email,
                transient_payload={},
            )
        )

        # Convert the login data to a dictionary
        login_data_dict = login_data.dict()

        # Convert cookies dictionary to a string
        cookies_str = "; ".join([f"{key}={value}" for key, value in request.cookies.items()])
        print(f"Cookies as string: {cookies_str}")

        # Send the login request to Kratos
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:4433/self-service/login?flow={flow}",
                json=login_data_dict["actual_instance"],
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Cookie": cookies_str,
                },
            )

            print(f"Raw Kratos response: {response.json()}")

            
            # Handle the response
            if response.status_code == 200:
                # Login successful
                print("Login successful")

                # Set the session cookie in the response
                session_cookie = response.cookies.get("ory_kratos_session")
                if session_cookie:
                    response = RedirectResponse(url="/dashboard", status_code=303)
                    response.set_cookie(
                        key="ory_kratos_session",
                        value=session_cookie,
                        httponly=True,
                        secure=True,  # Set to False if not using HTTPS
                        samesite="lax",
                    )
                    return response
                else:
                    raise HTTPException(status_code=500, detail="Session cookie not found in Kratos response")

            elif response.status_code == 400:
                # Handle form validation errors
                error_detail = response.json().get("error", {}).get("message", "Login failed")
                print(f"Login failed: {error_detail}")
                raise HTTPException(status_code=400, detail=error_detail)

            elif response.status_code == 410:
                # Handle expired flow
                error_detail = response.json().get("error", {}).get("message", "The login flow has expired")
                print(f"Login flow expired: {error_detail}")
                raise HTTPException(status_code=410, detail=error_detail)

            else:
                # Handle unexpected response types
                print(f"Unexpected response: {response.json()}")
                raise HTTPException(status_code=500, detail="Unexpected response from Kratos")

    except ValueError as ve:
        print(f"ValueError: {ve}")
        raise HTTPException(status_code=400, detail=f"Value Error: {ve}")

    except AttributeError as ae:
        print(f"AttributeError: {ae}")
        raise HTTPException(status_code=400, detail=f"Attribute Error: {ae}")

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=f"Data serialization error: {e}")
    
@app.get("/verify-flow")
async def verify_flow(request: Request, flow_id: str):
    """
    Fetches and verifies the registration flow details.
    """
    try:
        flow = frontend_api.get_registration_flow(
            id=flow_id,
            cookie=request.headers.get("cookie")  # Pass cookies for CSRF validation
        )
        return flow.to_dict()
    except ApiException as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.get("/verify-flow-login")
async def verify_flow_login(request: Request, flow_id: str):
    """
    Fetches and verifies the registration flow details.
    """
    try:
        flow = frontend_api.get_login_flow(
            id=flow_id,
            cookie=request.headers.get("cookie")  # Pass cookies for CSRF validation
        )
        return flow.to_dict()
    except ApiException as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
 

@app.get("/registration")
async def show_registration_form(request: Request):
    print("i am in show_registration_form")
    print(f"request: {request}")
    
     # Check if the session cookie is present and valid
    if "ory_kratos_session" in request.cookies:
        session_response = requests.get(
            f"{KRATOS_EXTERNAL_API_URL}/sessions/whoami",
            cookies=request.cookies
        )
        if session_response.status_code == 200 and session_response.json().get("active"):
            return RedirectResponse(url="/dashboard")
    
    form_data = await request.form()
    
    # Convert form data to a dictionary
    form_dict = dict(form_data)
    
    # Log or process the form data
    print("Form Data:", form_dict)
    try:
        async with httpx.AsyncClient() as client:
            cookies = request.cookies
            headers = {
                "Accept": "application/json",
            }

            response = await client.get(
                "http://127.0.0.1:4433/self-service/registration/browser",
                cookies=cookies,
                headers=headers
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch registration flow")

            flow_data = response.json()
            print(f"flow_data: {flow_data}")
            print(f"flow_id: {flow_data['id']}")
            csrf_token = None

            for node in flow_data['ui']['nodes']:
                attributes = node['attributes']
                if attributes.get('name') == "csrf_token":
                    csrf_token = attributes['value']
                    break

            if not csrf_token or not flow_data['id']:
                raise HTTPException(status_code=400, detail="CSRF token or Flow ID is missing.")

            return templates.TemplateResponse(
                "registration.html",
                {
                    "request": request,
                    "flow_id": flow_data['id'],
                    "csrf_token": csrf_token,
                }
            )

    except Exception as e:
        print(f"Error fetching registration flow: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
@app.post("/registration")
async def handle_registration(
    request: Request,
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    password: str = Form(...),
    flow: str = Form(...),
    csrf_token: str = Form(...)
):
    print("i am in update_registration_flow")
    print(f"email: {email}")
    print(f"first_name: {first_name}")
    print(f"last_name: {last_name}")
    print(f"password: {password}")
    print(f"flow: {flow}")
    print(f"csrf_token: {csrf_token}")

    try:
        # Prepare the registration data
        registration_data = UpdateRegistrationFlowBody(
            actual_instance=UpdateRegistrationFlowWithPasswordMethod(
                csrf_token=csrf_token,
                password=password,
                method="password",
                traits={"email": email, "name": {"first": first_name, "last": last_name}},
                transient_payload={},
            )
        )

        # Convert the registration data to a dictionary
        registration_data_dict = registration_data.dict()

        # Convert cookies dictionary to a string
        cookies_str = "; ".join([f"{key}={value}" for key, value in request.cookies.items()])
        print(f"Cookies as string: {cookies_str}")

        # Send the registration request to Kratos
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:4433/self-service/registration?flow={flow}",
                json=registration_data_dict["actual_instance"],
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Cookie": cookies_str,
                },
            )

            print(f"Raw Kratos response: {response.json()}")

            # Handle the response
            if response.status_code == 200:
                # Registration successful
                print("Registration successful")
                return RedirectResponse(url="http://127.0.0.1:4433/self-service/login/browser", status_code=303)

            elif response.status_code == 400:
                # Handle form validation errors
                error_detail = response.json().get("error", {}).get("message", "Registration failed")
                print(f"Registration failed: {error_detail}")
                raise HTTPException(status_code=400, detail=error_detail)

            elif response.status_code == 410:
                # Handle expired flow
                error_detail = response.json().get("error", {}).get("message", "The registration flow has expired")
                print(f"Registration flow expired: {error_detail}")
                raise HTTPException(status_code=410, detail=error_detail)

            else:
                # Handle unexpected response types
                print(f"Unexpected response: {response.json()}")
                raise HTTPException(status_code=500, detail="Unexpected response from Kratos")

    except ValueError as ve:
        print(f"ValueError: {ve}")
        raise HTTPException(status_code=400, detail=f"Value Error: {ve}")

    except AttributeError as ae:
        print(f"AttributeError: {ae}")
        raise HTTPException(status_code=400, detail=f"Attribute Error: {ae}")

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=f"Data serialization error: {e}")




# Logout route
@app.get("/logout")
async def create_logout_flow(request: Request):
    """
    Handles GET requests to initiate the logout flow.
    """
    # Check if the session cookie is present
    if "ory_kratos_session" not in request.cookies:
        return RedirectResponse(url="/", status_code=303)

    # Verify the session with Kratos
    session_response = httpx.get(
        f"{KRATOS_EXTERNAL_API_URL}/sessions/whoami",
        cookies=request.cookies
    )

    # If the session is active, create a logout flow
    if session_response.status_code == 200 and session_response.json().get("active"):
        try:
            async with httpx.AsyncClient() as client:
                # Create a browser logout flow
                logout_response = await client.get(
                    f"{KRATOS_EXTERNAL_API_URL}/self-service/logout/browser",
                    cookies=request.cookies
                )

                if logout_response.status_code != 200:
                    raise HTTPException(status_code=logout_response.status_code, detail="Failed to create logout flow")

                # Extract the logout URL from the response
                logout_url = logout_response.json().get("logout_url")
                if not logout_url:
                    raise HTTPException(status_code=400, detail="Logout URL is missing")

                # Redirect the user to the logout URL
                return RedirectResponse(url=logout_url, status_code=303)

        except Exception as e:
            print(f"Error creating logout flow: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    # If the session is not active, redirect to the home page
    return RedirectResponse(url="/", status_code=303)


@app.post("/update_logout")
async def update_logout(request: Request):
    """
    Handles POST requests to update or complete the logout flow.
    """
    try:
        # Extract the logout token or flow ID from the request
        form_data = await request.form()
        logout_token = form_data.get("logout_token")

        if not logout_token:
            raise HTTPException(status_code=400, detail="Logout token is missing")

        # Perform additional actions (e.g., logging, cleanup)
        print(f"Logout token received: {logout_token}")

        # Optionally, you can verify the logout token with Kratos
        async with httpx.AsyncClient() as client:
            verify_response = await client.post(
                f"{KRATOS_EXTERNAL_API_URL}/self-service/logout",
                json={"logout_token": logout_token}
            )

            if verify_response.status_code != 200:
                raise HTTPException(status_code=verify_response.status_code, detail="Failed to verify logout token")

        # Return a success response
        return {"message": "Logout flow updated successfully"}

    except Exception as e:
        print(f"Error updating logout flow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")







# @app.post("/login")
# async def login_user(email: str = Form(...), password: str = Form(...)):
#     # Step 1: Initiate login flow
#     login_flow = await initiate_login_flow()
    
#     # Step 2: Complete login with provided email and password
#     login_response = await complete_login_flow(
#         flow_id=login_flow.id,
#         email=email,
#         password=password
#     )
    
#     # Return the login result (session token, identity)
#     return JSONResponse(content=login_response.to_dict())

# # Optionally, add an endpoint to fetch identity information
# @app.get("/identity/{identity_id}")
# async def get_identity(identity_id: str):
#     try:
#         identity = await identity_api.get_identity(identity_id)
#         return JSONResponse(content=identity.to_dict())
#     except ApiException as e:
#         raise HTTPException(status_code=e.status, detail=e.body)

