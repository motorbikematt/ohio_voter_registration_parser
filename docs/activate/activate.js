const urlParams = new URLSearchParams(window.location.search);
const apiOverride = urlParams.get('captainApi');
const API_BASE = apiOverride 
  ? apiOverride
  : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://127.0.0.1:8000'
      : 'https://precincts.info/api');

document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const v_id = urlParams.get('v_id');
  const needs_phone = urlParams.get('needs_phone') === 'true';

  if (v_id) {
    document.getElementById('v_id').value = v_id;
  }

  if (needs_phone) {
    const pinInput = document.getElementById('pin');
    const phoneLabel = document.getElementById('phoneLabel');
    const helpText = document.getElementById('phoneHelpText');
    
    phoneLabel.textContent = '10-Digit Cell Phone Number';
    pinInput.placeholder = '5551234567';
    pinInput.maxLength = 10;
    helpText.textContent = 'Please enter your full 10-digit cell phone number.';
  } else {
    const pinInput = document.getElementById('pin');
    pinInput.maxLength = 4;
  }

  document.getElementById('activateForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submitBtn');
    const btnSpan = submitBtn.querySelector('span');
    const errorBox = document.getElementById('errorMessage');
    const successBox = document.getElementById('successMessage');
    
    errorBox.classList.add('hidden');
    successBox.classList.add('hidden');

    const pin = document.getElementById('pin').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    if (password !== confirmPassword) {
      errorBox.textContent = 'Passwords do not match.';
      errorBox.classList.remove('hidden');
      return;
    }

    if (needs_phone && pin.length !== 10) {
      errorBox.textContent = 'Please enter a valid 10-digit phone number.';
      errorBox.classList.remove('hidden');
      return;
    } else if (!needs_phone && pin.length !== 4) {
      errorBox.textContent = 'Please enter your 4-digit PIN.';
      errorBox.classList.remove('hidden');
      return;
    }

    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-75', 'cursor-not-allowed');
    btnSpan.textContent = 'Activating...';

    try {
      const response = await fetch(`${API_BASE}/activate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          v_id: document.getElementById('v_id').value,
          pin: pin,
          new_password: password
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to activate account.');
      }

      // Success
      successBox.classList.remove('hidden');
      document.getElementById('activateForm').reset();
      
      // Optionally save token
      if (data.token) {
        localStorage.setItem('captain_token', data.token);
      }

      // Redirect to canvassing dashboard
      setTimeout(() => {
        const nextUrl = new URL('../captain', window.location.href);
        if (apiOverride) {
          nextUrl.searchParams.set('captainApi', apiOverride);
        }
        window.location.href = nextUrl.toString();
      }, 2000);

    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.classList.remove('hidden');
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
      btnSpan.textContent = 'Activate Account';
    }
  });
});
