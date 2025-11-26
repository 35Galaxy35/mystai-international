import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
import { 
  getAuth, 
  onAuthStateChanged, 
  signOut 
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";

import {
  getFirestore,
  collection,
  getDocs,
  updateDoc,
  doc
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyDyiD7GAfOjMbtm-S6pO6XCSRXJclffPL0",
  authDomain: "mystai-6cca2.firebaseapp.com",
  projectId: "mystai-6cca2",
  storageBucket: "mystai-6cca2.appspot.com",
  messagingSenderId: "624127781219",
  appId: "1:624127781219:web:a580ac6e80ccc26e694b56"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// ADMIN E-MAIL
const ADMIN_EMAIL = "chf.ethem35belen@outlook.com";

// Admin Sayfası Güvenliği
onAuthStateChanged(auth, async (user) => {
  if (!user || user.email !== ADMIN_EMAIL) {
    alert("Bu sayfa yalnızca yöneticiler içindir.");
    window.location.href = "login.html";
    return;
  }

  loadUsers();
  loadFortunes();
});

// Kullanıcıları Yükle
async function loadUsers() {
  const userTable = document.getElementById("userTable");
  userTable.innerHTML = "";

  const usersRef = collection(db, "users");
  const snapshot = await getDocs(usersRef);

  snapshot.forEach((docSnap) => {
    const data = docSnap.data();

    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${data.email}</td>
      <td>${data.freeUsed ? "Evet" : "Hayır"}</td>
      <td>${data.premium ? "Aktif" : "Pasif"}</td>
      <td>
        <button onclick="setFree('${docSnap.id}', false)">Ücretsiz Hakkı Sıfırla</button>
        <button onclick="setPremium('${docSnap.id}', true)">Premium Yap</button>
      </td>
    `;

    userTable.appendChild(tr);
  });
}

// Fal Geçmişi Yükle
async function loadFortunes() {
  const table = document.getElementById("fortuneTable");
  table.innerHTML = "";

  const ref = collection(db, "fortunes");
  const snapshot = await getDocs(ref);

  snapshot.forEach((docSnap) => {
    const d = docSnap.data();

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${d.user}</td>
      <td>${d.type}</td>
      <td>${d.question}</td>
      <td>${d.createdAt?.toDate ? d.createdAt.toDate().toLocaleString() : "-"}</td>
    `;
    table.appendChild(tr);
  });
}

// Ücretsiz hakkı sıfırlama
window.setFree = async function (uid, val) {
  await updateDoc(doc(db, "users", uid), { freeUsed: val });
  alert("Kullanıcı güncellendi.");
  loadUsers();
};

// Premium yapma
window.setPremium = async function (uid, val) {
  await updateDoc(doc(db, "users", uid), { premium: val });
  alert("Kullanıcı premium yapıldı.");
  loadUsers();
};

document.getElementById("logoutBtn").addEventListener("click", () => {
  signOut(auth);
});
