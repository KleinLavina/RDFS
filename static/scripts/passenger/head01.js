(function(){
  const toggle = document.querySelector('.rdfs-header__toggle');
  const nav = document.querySelector('.rdfs-header__nav');

  if(!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', open);
  });

  document.addEventListener('click', e => {
    if(!nav.contains(e.target) && !toggle.contains(e.target)){
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded','false');
    }
  });

  document.addEventListener('keydown', e => {
    if(e.key === 'Escape'){
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded','false');
    }
  });
})();