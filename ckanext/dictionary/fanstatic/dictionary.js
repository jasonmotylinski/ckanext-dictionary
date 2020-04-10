ckan.module('dictionary_add_field', function ($) {
    return {
      initialize: function () {
        $(function(){
            $( "#btn-add" ).click(function() {
              $('.control-group:last').after($('.control-group:last').clone());
              $('.control-group:last input').val('');
            });
          });
      }
    };
});