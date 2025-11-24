(function () {
    // Kullanıcının tarayıcı dilini al
    const userLang = navigator.language || navigator.userLanguage;

    // Eğer kullanıcı admin paneldeyse yönlendirme yapma
    if (window.location.pathname.includes("login") ||
        window.location.pathname.includes("signup") ||
        window.location.pathname.includes("profile")) {
        return;
    }

    // Eğer kullanıcı zaten tercih yaptıysa tekrar yönlendirme yapma
    if (localStorage.getItem("preferredLang")) {
        return;
    }

    // Kullanıcı Türkçe ise TR sayfalarına göndersin
    if (userLang.startsWith("tr")) {
        window.location.href = window.location.pathname.replace(".html", "-tr.html");
    } 
    // Türkçe değilse default İngilizce kalsın
})();
