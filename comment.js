var label = document.querySelectorAll('label')[0];
var allowSubmit = true;

function lengthCheck() {
  allowSubmit = this.getAttribute('value').length <= 99;
  if (!allowSubmit) {
    label.innerHTML = 'Comment too long!';
  }
}

form = document.querySelectorAll('form')[0];
if (form) {
  form.addEventListener('submit', function (e) {
    if (!allowSubmit) {
      e.preventDefault();
    }
  });
}

input = document.querySelectorAll('input')[0];
if (input) {
  input.addEventListener('keydown', lengthCheck);
}

// x = new XMLHttpRequest();
// x.open('GET', 'http://localhost:8000/', false);
// x.send();
// console.log(x.responseText);
// user = x.responseText.split(' ')[2].split('<')[0];
