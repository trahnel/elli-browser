var label = document.querySelectorAll('label')[0];
var allowSubmit = true;

function lengthCheck() {
  allowSubmit = this.getAttribute('value').length <= 99;
  if (!allowSubmit) {
    label.innerHTML = 'Comment too long!';
  }
}

form = document.querySelector('form')[0];
form.addEventListener('submit', function (e) {
  if (!allowSubmit) {
    e.preventDefault();
  }
});

input = document.querySelectorAll('input')[0];
input.addEventListener('keydown', lengthCheck);
