<script>
$(function(){
  $( "#btn-add" ).click(function() {
    $('.control-group:last').after($('.control-group:last').clone());
  });
});
</script>