var Backbone = require('backbone'),
    template = require("../templates/login.hbs"),
    i18n = require('i18next-client'),
    config = require('../config'),
    $ = require('jquery')
;

$(function() {
    toggleLoginMenuItem();
})

function toggleLoginMenuItem() {
    if (config.get('forever.authToken')) {
        $('.menu-item-login').hide();
        $('.menu-item-logout').show();
    } else {
        $('.menu-item-login').show();
        $('.menu-item-logout').hide();

        // TODO: Remove this later
        window.location.hash = 'login';
    }
};

module.exports = Backbone.View.extend({
    initialize: function(){
        this.render();
    },

    render: function() {
        var $el = this.$el;
        this.$el.html(template({}));
    },

    events: {
        "click button": function(ev) {
            var $el = this.$el;
            ev.preventDefault();
            var data = {
                email: $el.find('[name=email]').val(),
                password: $el.find('[name=password]').val(),
            };

            $.ajax(config.get('api_location') + 'api/login/', {
                method: 'POST',
                type: 'JSON',
                data: data,
                error: function(e) {
                    console.error("login fail:", e.responseJSON);
                    $('.error').text('');
                    for (var k in e.responseJSON) {
                        if (k == 'non_field_errors') {
                            $el.find('.non-field-errors').text(e.responseJSON[k]);
                        } else if (e.responseJSON.hasOwnProperty(k)) {
                            $el.find('.error-' + k).text(e.responseJSON[k]);
                        }
                    }
                },
                success: function(data) {
                    config.set('forever.authToken', data.token);
                    toggleLoginMenuItem();
                    window.location.hash = 'service';
                },
            })
        }
    }
})