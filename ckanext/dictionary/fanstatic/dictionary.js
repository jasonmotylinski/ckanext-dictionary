ckan.module('dictionary_add_field', function ($) {
    return {
      initialize: function () {
        $(function(){
            $( "#btn-add" ).click(function() {
                $('.control-group:last').after($('.control-group:last').clone());
                $('.control-group:last input').val('');

                $('.control-group').each(function(idx, el){
                    $(el).find('input').each(function(idx2, el2){
                        $(el2).attr('id',$(el2).attr('class') + "-" + idx);
                        $(el2).attr('name', $(el2).attr('class') + "_" + idx);
                    });
                });
            });
        });
      }
    };
});