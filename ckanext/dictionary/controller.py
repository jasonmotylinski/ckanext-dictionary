"""Summary: Controllers for Dictionary Plugin for CKAN.

Description:  ApiController handles API logic. DDController contains the UI logic.
"""
import logging
import ckan.lib.helpers as h
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
import ckan.lib.plugins
import ckan.lib.render

from ckan.authz import is_authorized
from ckan.common import _, json, request, c, g, response
from ckan.lib.base import BaseController
from ckan.views import identify_user
from ckanext.dictionary import action

log = logging.getLogger(__name__)

render = base.render
abort = base.abort

NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params
flatten_to_string_key = logic.flatten_to_string_key

lookup_package_plugin = ckan.lib.plugins.lookup_package_plugin

class ApiController(BaseController):
    """Controller for API actions."""

    def get_context(self):
        """Context of the API request."""
        identify_user()

        return {'model': model, 
                'user': g.user,
                'author': g.author,
                'ignore_auth': True,
                'auth_user_obj': g.userobj}

    def dictionary_update(self):
        """Update the dictionary for a given package."""
        context=self.get_context()
        log.info("dictionary_update:context:{0}".format(context))
        try:
            if request.method == 'POST':
                log.info("dictionary_update:POST:Content-Type:{0}".format(request.content_type))
                log.info("dictionary_update:request.body:{0}".format(request.body))

                check_access('update_data_dictionary', context)
                response.status_int = 200
                response.headers['Content-Type'] = "application/json"
                return json.dumps({"success": True})
            else:
                response.status_int = 501
                response.headers['Content-Type'] = "application/json"
                return json.dumps({"success": False ,"error": {"messsage": "Not Implemented"}})
        except NotAuthorized as e:
            response.status_int = 403
            response.headers['Content-Type'] = "application/json"
            log.error("dictionary_update:NotAuthorized: {0}".format(e.message))
            return json.dumps({"success": False ,"error": {"messsage": "NotAuthorized"}})   
        except Exception as e:
            response.status_int = 500
            response.headers['Content-Type'] = "application/json"
            log.error("dictionary_update:Exception: {0}".format(e.message))
            return json.dumps({"success": False ,"error": {"messsage": "Exception"}})   


class DDController(BaseController):
    """Controller used for UI logic."""

    def get_context(self):
        """Get the context object used by CKAN actions."""
        return {'model': model,
                'session': model.Session,
                'user': c.user or c.author,
                'auth_user_obj': c.userobj}


    def _resource_form(self, package_type):
        """Backwards compatibility with plugins not inheriting from DefaultDatasetPlugin and not implmenting resource_form."""
        plugin = lookup_package_plugin(package_type)
        if hasattr(plugin, 'resource_form'):
            result = plugin.resource_form()
            if result is not None:
                return result
        return lookup_package_plugin().resource_form()


    def edit_dictionary(self, id, data=None, errors=None):
        """Edit dictionary."""
        context=self.get_context()
        context['for_view']=True
        context['use_cache']=False

        resource_id=action.get_data_dict_resource_id(context)
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id': id}, 'sort': ['id']}

        try:
            pkg_data_dictionary = get_action('datastore_search')(context, data_dict_dict)
            c.pkg_data_dictionary = pkg_data_dictionary['records']
            c.link = str("/dataset/dictionary/new_dict/" + id)
            c.pkg_dict = get_action('package_show')(context, {'id': id})
            c.pkg = context['package']
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read dataset %s') % id)
        return render("package/edit_data_dict.html", extra_vars={'package_id': id})

    def get_row_count_from_params(self):
        """Determine how many form rows are being passed in via HTTP parameters."""
        idx = 0
        while True:
            id = request.params.get("field_{0}".format(idx))
            if id is None or id == '':
                break
            else:
                idx = idx + 1
        log.info("get_row_count_from_params: Row count: {0}".format(idx))
        return idx

    def get_record_from_params(self, package_id, resource_id, row_id):
        """Build a record object from request parameters."""
        varNames = ['field_' + str(row_id), 'type_' + str(row_id), 'description_' + str(row_id), 'title_' + str(row_id), 'format_' + str(row_id)]
        datafield = request.params.get(varNames[0])
        datadesc = request.params.get(varNames[2])
        datatitle = request.params.get(varNames[3])
        dataformat = request.params.get(varNames[4])
        return {'field_name': datafield, 'description': datadesc, "title": datatitle, "format": dataformat}

    def new_data_dictionary(self, id):
        """Update the data dictionary for a given package from the web for."""
        package_id = id  # I'm not usually a fan of reassigning variables for no reason, but there are a lot of IDs floating around in this function so reassigning for clarity

        log.info("new_data_dictionary: Package ID: {0}".format(package_id))

        if request.method == 'POST':
            context = self.get_context()
            resource_id = action.get_data_dict_resource_id(context)

            try:
                rowCount = self.get_row_count_from_params()
                data = {"records": [], "package_id": package_id}
                if rowCount > 0:
                    for i in range(0, rowCount):
                        data['records'].append(self.get_record_from_params(data['package_id'], resource_id, i))

                    action.update_data_dictionary(context, data)
            except NotFound:
                abort(404, _('Dataset not found'))
            except NotAuthorized:
                abort(401, _('Unauthorized to read dataset %s') % id)

            h.redirect_to(controller='package', action='read', id=id)

    def dictionary(self, id):
        """Render logic for displaying the dictionary for a given package."""
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'for_view': True,
                   'auth_user_obj': c.userobj, 'use_cache': False}
        data_dict = {'id': id}
        try:
            log.info("dictionary: trying to get the data_dict")
            c.pkg_dict = get_action('package_show')(context, data_dict)
            dataset_type = c.pkg_dict['type'] or 'dataset'
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read dataset %s') % id)

        context = self.get_context()

        resource_id = action.get_data_dict_resource_id(context)
                
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id':id},'sort':['id']}
        pkg_data_dictionary = get_action('datastore_search')(context, data_dict_dict)
        print(pkg_data_dictionary['records'])
        c.pkg_data_dictionary = pkg_data_dictionary['records']

        return render('package/dictionary_display.html', {'dataset_type': dataset_type})
