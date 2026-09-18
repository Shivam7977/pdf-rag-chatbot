from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class LoginRequest(BaseModel):
    email: EmailStr
    # No min_length here (unlike SignupRequest/SetPasswordRequest) — this
    # validates an EXISTING password being submitted for login, not a new
    # one being created. Enforcing a length-minimum here would wrongly
    # reject correct logins for any account whose password predates this
    # policy.
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"