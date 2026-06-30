/**
 * activate.js
 * 
 * Handles the Canvassing Dashboard account activation flow.
 * Extracts the user's UUID (v_id) from the URL and prompts them for their full 10-digit 
 * cell phone number and a new password. The phone number acts as an MFA/identity verification
 * step. If successful, redirects the user to their private dashboard (/captain).
 */
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

  if (v_id) {
    document.getElementById('v_id').value = v_id;
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

    if (pin.length !== 10) {
      errorBox.textContent = 'Please enter a valid 10-digit phone number.';
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
