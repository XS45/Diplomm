// Функция для приветствия
async function sayHello() {
    const name = document.getElementById("name").value;

    try {
        const response = await fetch(`/api/hello?name=${encodeURIComponent(name)}`);
        const data = await response.json();

        document.getElementById("resultText").textContent = data.message;
        document.getElementById("result").classList.add("active");
    } catch (error) {
        console.error("Ошибка:", error);
        document.getElementById("resultText").textContent = "Ошибка при запросе к серверу";
        document.getElementById("result").classList.add("active");
    }
}

// Функция для получения списка пользователей
async function getUsers() {
    try {
        const response = await fetch("/api/users");
        const users = await response.json();

        let html = "<div class='users-list'><h3>Пользователи:</h3>";
        users.forEach(user => {
            html += `<div class="user-item"><strong>${user.name}</strong> (ID: ${user.id})</div>`;
        });
        html += "</div>";

        document.getElementById("usersList").innerHTML = html;
    } catch (error) {
        console.error("Ошибка:", error);
        document.getElementById("usersList").innerHTML = "<p>Ошибка при загрузке пользователей</p>";
    }
}

// Позволяем нажимать Enter в поле ввода
document.getElementById("name")?.addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sayHello();
    }
});
