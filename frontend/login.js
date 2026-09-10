const API_BASE = ""; // same-origin; change if frontend is ever served separately from the API
const GOOGLE_CLIENT_ID = "156200876984-2egnbobauansfgn11lj06vtobqruhe3l.apps.googleusercontent.com";

let mode = "login"; // "login" | "signup"
let pendingEmail = "";

const tabLogin = document.getElementById("tab-login");
const tabSignup = document.getElementById("tab-signup");
const authForm = document.getElementById("auth-form");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");

const stepForm = document.getElementById("auth-step-form");
const stepVerify = document.getElementById("auth-step-verify");
const verifyForm = document.getElementById("verify-form");
const verifyCode = document.getElementById("verify-code");
const verifyError = document.getElementById("verify-error");
const verifyEmailDisplay = document.getElementById("verify-email-display");

const guestBtn = document.getElementById("guest-btn");

tabLogin.addEventListener("click", () => setMode("login"));
tabSignup.addEventListener("click", () => setMode("signup"));

function setMode(newMode) {
  mode = newMode;
  tabLogin.classList.toggle("is-active", mode === "login");
  tabSignup.classList.toggle("is-active", mode === "signup");
  authSubmit.textContent = mode === "login" ? "Log in" : "Sign up";
  authPassword.autocomplete = mode === "login" ? "current-password" : "new-password";
  hideError(authError);
}

function showError(el, message) {
  el.textContent = message;
  el.hidden = false;
}
function hideError(el) {
  el.hidden = true;
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong.");
  return data;
}

async function startAppSession(token) {
  // Every login/signup/google flow ends the same way: we have a JWT, now
  // create a fresh saved chat and hand off to app.html.
  const res = await fetch(API_BASE + "/chats", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  localStorage.setItem("docquery_token", token);
  localStorage.setItem("docquery_chat_session_id", data.chat_session_id);
  window.location.href = "app.html";
}

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError(authError);
  const email = authEmail.value.trim();
  const password = authPassword.value;

  try {
    if (mode === "login") {
      const data = await apiPost("/auth/login", { email, password });
      await startAppSession(data.access_token);
    } else {
      await apiPost("/auth/signup", { email, password });
      pendingEmail = email;
      verifyEmailDisplay.textContent = email;
      stepForm.hidden = true;
      stepVerify.hidden = false;
      verifyCode.focus();
    }
  } catch (err) {
    showError(authError, err.message);
  }
});

verifyForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError(verifyError);
  try {
    const data = await apiPost("/auth/verify-signup", {
      email: pendingEmail,
      code: verifyCode.value.trim(),
    });
    await startAppSession(data.access_token);
  } catch (err) {
    showError(verifyError, err.message);
  }
});

guestBtn.addEventListener("click", async () => {
  try {
    const res = await fetch(API_BASE + "/auth/guest", { method: "POST" });
    const data = await res.json();
    localStorage.removeItem("docquery_token"); // guests hold no token
    localStorage.setItem("docquery_chat_session_id", data.chat_session_id);
    window.location.href = "app.html";
  } catch (err) {
    showError(authError, "Couldn't start a guest session. Try again.");
  }
});

// --- Google Sign-In ---
window.onload = () => {
  if (!window.google) return; // script blocked/offline — Google button just won't render
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
  });
  google.accounts.id.renderButton(document.getElementById("google-btn"), {
    theme: "outline",
    size: "large",
    width: 320,
  });
};

async function handleGoogleCredential(response) {
  try {
    const data = await apiPost("/auth/google", { id_token: response.credential });
    await startAppSession(data.access_token);
  } catch (err) {
    showError(authError, err.message);
  }
}