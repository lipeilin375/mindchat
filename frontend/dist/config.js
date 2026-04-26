// const base_url = "http://127.0.0.1:8000"
const base_url = "https://api.mindchat.dpdns.org"

function clearTempStorage() {
    localStorage.removeItem('mindchat_token');
    localStorage.removeItem('mindchat_user');
    sessionStorage.clear();
}